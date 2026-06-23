# YOLOv8n TFLite Export 환경 수정 기록

> 본 문서는 Ultralytics export를 수행하던 중 발생한 환경 충돌 사고와 해결 과정을 기록합니다.
> 당초 채택했던 TF 2.13.0 핀과 현재(2026-06-23) Ultralytics 버전 간의 의존성 변화가 원인이며, 본 작품의 `Dockerfile`/`requirements.txt`를 갱신하여 해결합니다.

---

## 결정 요약 (한 화면)

| 항목 | 내용 |
|---|---|
| 발생 사건 | Ultralytics export 실행 중 환경 자동 변경으로 export 실패 |
| 1차 실패 원인 | TF 2.13.0 import 후 TF 2.19.1 mid-process 교체 → KerasTensor 비호환 에러 |
| 2차 실패 원인 | numpy 1.24.3 → 2.1.3 자동 업그레이드 → torch 2.1.2 (numpy 1.x 빌드) ABI 비호환 |
| 근본 원인 | Ultralytics가 export 시 transitive deps를 `pip install --user` 로 강제 업그레이드 (`tf_keras<=2.19.0` 요구가 TF 2.19, numpy 2.1을 끌고 옴) |
| 해결 | 모든 transitive deps를 사전에 `requirements.txt`에 핀 → AutoUpdate 차단 → 컨테이너 재빌드 |
| 당초 TF 2.13.0 핀과의 차이 | 당초 핀은 과거 Ultralytics 버전 기준. 현재 8.4.75와는 호환 불가 |

---

## 1. 사건 타임라인

### 1차 시도 (2026-06-23, 약 16:21 UTC)

명령:
```bash
python -c "from ultralytics import YOLO; m=YOLO('yolov8n.pt'); m.export(format='tflite', int8=True, imgsz=320, data='coco128.yaml')"
```

진행:
- yolov8n.pt, coco128.zip 다운 정상
- ONNX export 정상 완료
- Ultralytics가 누락 deps 자동 설치 시작: `onnxslim`, `onnx2tf`, `tf_keras`, `sng4onnx`, `onnx_graphsurgeon`, `ai-edge-litert`, `protobuf>=5`
- 이 과정에서 다음 패키지 강제 교체:
  - `tensorflow` 2.13.0 → 2.19.1
  - `numpy` 1.24.3 → 2.1.3
  - `keras` 2.13.1 → 3.12.2
  - `tensorboard` 2.13.0 → 2.19.0
  - `protobuf` 4.25.9 → 5.29.6
- 매 설치 후 경고: `WARNING ⚠️ Restart runtime or rerun command for updates to take effect`
- 그러나 같은 프로세스가 계속 진행
- onnx2tf가 TFLite 변환 시도 → `KerasTensor` 비호환 에러로 실패

에러 핵심:
```
TypeError: You are passing KerasTensor(...), an intermediate TF-Keras symbolic input/output,
to a TF API that does not allow registering custom dispatchers ...
ERROR: onnx_op_name: wa/model.10/Resize
```

원인 추정: TF 2.13의 일부 모듈이 메모리에 남은 상태에서 TF 2.19의 모듈이 새로 import되어 일관성 깨짐.

### 2차 시도 (재실행으로 환경 정리 기대)

명령: (동일)

진행:
- 새 프로세스 시작
- 패키지는 디스크 상 TF 2.19 + numpy 2.1.3 상태
- `import ultralytics` → 내부 `import torch` → 실패

에러 핵심:
```
RuntimeError: Numpy is not available
UserWarning: Failed to initialize NumPy: _ARRAY_API not found
```

원인: 컨테이너 빌드 시 설치된 torch 2.1.2는 numpy 1.x ABI에 컴파일됨. numpy 2.x와는 바이너리 호환 X. Ultralytics가 numpy 2.1.3을 깐 시점에 torch는 사용 불가 상태.

---

## 2. 근본 원인 분석

### 2-1. Ultralytics의 AutoUpdate 정책

Ultralytics는 export 단계에서 필요한 도구가 없으면 **현재 사용자 환경에 `pip install --user`로 자동 설치**합니다. 이는:
- 추가 옵션 없이도 export가 "그냥 되게" 만들기 위한 편의
- 그러나 **이미 핀된 환경을 강제로 변경**하는 부작용

특히 `tf_keras<=2.19.0` 요구가 transitive하게:
- `tensorflow>=2.19` (tf_keras 의존)
- `numpy>=1.26,<2.2` (TF 2.19 의존)
- `keras>=3.5` (TF 2.19 의존)
까지 끌고 옴.

### 2-2. 당초 `tensorflow==2.13.0` 핀의 한계

본 프로젝트는 초기에 일반적인 Ultralytics 안정 환경 권고에 따라 `tensorflow==2.13.0`을 핀했습니다. 이는 과거 Ultralytics 8.0.x 시점에 안정적이었던 조합으로 알려진 것이나, 현재(2026-06-23) Ultralytics 8.4.75는 내부 export 체인이 TF 2.19를 요구하도록 변경됨.

→ 당초 핀을 그대로 두면 1차 충돌은 필연.

### 2-3. torch 바이너리 ABI 호환성

torch는 미리 컴파일된 wheel (.whl)로 배포되며, numpy 메이저 버전(1.x vs 2.x)에 ABI가 강하게 묶임:
- torch 2.1.x → numpy 1.x 빌드
- torch 2.4+ → numpy 2.x 호환

우리는 torch 2.1.2를 쓰므로 numpy<2 필수.
torch 업그레이드는 CUDA/시스템 의존성 변경 가능성이 있어 회피.

---

## 3. 해결 — `requirements.txt` 갱신

### 변경 내용 (이전 → 이후)

```diff
- tensorflow==2.13.0
- ultralytics
- opencv-python-headless
- numpy<2
- onnx
- onnxruntime
- pyyaml
- tqdm
+ # Core scientific
+ numpy==1.26.4
+ opencv-python-headless
+ pyyaml
+ tqdm
+ pillow
+
+ # TensorFlow / Keras stack
+ tensorflow==2.19.1
+ tf_keras==2.19.0
+ keras==3.12.2
+ ai-edge-litert
+ protobuf>=5,<6
+ ml-dtypes
+
+ # Ultralytics + ONNX 변환 도구 체인
+ ultralytics
+ onnx
+ onnxruntime
+ onnxslim
+ onnx2tf
+ onnx_graphsurgeon
+ sng4onnx
```

### 버전 핀 근거

| 패키지 | 핀 버전 | 근거 |
|---|---|---|
| numpy | 1.26.4 | torch 2.1.x(<2) + TF 2.19(>=1.26) 교집합. 안정 LTS 라인 |
| tensorflow | 2.19.1 | Ultralytics가 요구하는 tf_keras 2.19.0과 짝 |
| tf_keras | 2.19.0 | Ultralytics export 요구 |
| keras | 3.12.2 | TF 2.19와 짝 (별도 Keras 3) |
| protobuf | >=5,<6 | TF 2.19 호환, 미래 6.x 변경 차단 |
| 나머지 | 핀 없음 | 빠른 자동 갱신 허용. AutoUpdate 차단 효과는 위 핀들로 충족 |

---

## 4. 재현 절차

### 호스트 측
1. 컨테이너 종료:
   ```bash
   exit
   ```
2. 위 갱신된 `requirements.txt`가 적용된 상태로 재빌드:
   ```bash
   cd /mnt/c/Project/unoq-companion-robot
   bash run.sh --rebuild
   ```
3. 첫 재빌드는 약 15분 소요 (TF 2.19 + 의존성 신규 다운 발생).

### 컨테이너 측 (재진입 후)
4. Export 재시도 (동일 명령):
   ```bash
   cd /work/models
   python -c "from ultralytics import YOLO; m=YOLO('yolov8n.pt'); m.export(format='tflite', int8=True, imgsz=320, data='coco128.yaml')"
   ```
5. AutoUpdate가 일어나지 않아야 정상 (이미 모든 deps 사전 설치됨).
6. 변환 진행 → `yolov8n_saved_model/` 디렉토리에 `.tflite` 파일들 생성 예상.

---

## 5. 알려진 잔여 위험

### 5-1. onnx2tf KerasTensor 버그 재발 가능성
1차 시도에서 본 `KerasTensor` 에러는 환경 일관성 깨짐 외에 **onnx2tf 자체의 YOLOv8 Resize op 처리 문제일 가능성**도 있음 (PINTO0309/onnx2tf 알려진 이슈).

만약 재빌드 후에도 동일 에러 재발 시 대응 옵션:
- `model.export(...)`에 추가 인자 시도 (onnx2tf 우회 옵션 일부 노출됨)
- onnx2tf 버전 다운그레이드 (1.25.x ~ 1.26.x)
- 또는 onnx2tf를 우회하고 onnx → TF SavedModel을 다른 도구(예: `onnx-tf`)로 처리

### 5-2. Ultralytics 및 transitive deps 버전 변동
`requirements.txt`의 `ultralytics`, `torch` 등은 핀 없음. 향후 새 transitive dep 요구가 추가되면 빌드마다 환경이 달라질 가능성. **2026-06-23 export 성공 시점에 `pip freeze`로 lock 파일 생성하여 본 위험 해소** (Section 7 참조).

---

## 6. 학습 포인트

본 사고는 Python 패키징 생태계에서 흔히 발생하는 함정의 전형입니다:

- **상위 도구의 AutoUpdate**가 사용자의 핀된 환경을 침범하는 경우
- **사전 컴파일된 wheel** 간의 ABI 비호환 (특히 numpy 메이저 버전 경계)
- **mid-process 패키지 교체** 시 모듈 import 일관성 깨짐

이러한 함정은 **모든 transitive deps를 사전에 명시적으로 핀**하는 것으로 1차 방어 가능. `requirements.txt`로 주요 패키지만 핀하는 것은 부분 방어이며, 완전한 재현성은 다음 섹션의 lock 파일 적용으로 확보.

---

## 7. Lock 파일을 통한 byte-exact 재현성 확보

### 7-1. 배경
Section 5-2에서 예고한 잔여 위험 (ultralytics, torch 등 비핀 패키지의 버전 변동)을 export 성공 시점에 lock 파일로 동결.

### 7-2. 절차
컨테이너 안에서:
```bash
cd /work
pip freeze > requirements.lock
```

이 명령은 현재 환경의 모든 설치된 패키지(94개)를 정확한 버전과 함께 캡쳐. 호스트의 `/mnt/c/Project/unoq-companion-robot/requirements.lock`에도 즉시 반영됨 (마운트).

### 7-3. Dockerfile 갱신
`Dockerfile` Section 5를 다음으로 변경:
```dockerfile
COPY --chown=${USER_UID}:${USER_GID} requirements.txt /tmp/requirements.txt
COPY --chown=${USER_UID}:${USER_GID} requirements.lock /tmp/requirements.lock
RUN pip3 install --user --upgrade pip setuptools wheel \
    && pip3 install --user -r /tmp/requirements.lock
```

핵심 변화:
- 실제 설치 출처: `requirements.txt` → `requirements.lock`
- `requirements.txt`는 사람이 읽기 좋은 "의도" 표현으로 보관 (실제 설치엔 사용 안 함)

### 7-4. 두 파일의 역할 분리

| 파일 | 용도 | 누가 읽나 |
|---|---|---|
| `requirements.txt` | 인간이 읽고 의도 파악 ("우리는 TF 2.19, ultralytics가 필요해") | 사람 |
| `requirements.lock` | 빌드 도구가 byte-exact 설치 | Docker / pip |

### 7-5. 효과
- 협업자가 본 저장소를 clone하여 `bash run.sh` 시 **2026-06-23 본 환경과 정확히 동일한 패키지 조합** 설치
- 향후 PyPI에서 동일 버전이 유지되는 한 시간이 흘러도 같은 결과
- Ultralytics나 torch가 새 버전을 발표해도 본 환경은 영향 없음

### 7-6. Lock 파일 갱신 시점
- 의도적으로 의존성 업그레이드할 때 (예: 새 기능 필요 시)
  → `requirements.txt` 갱신 → `bash run.sh --rebuild` → 컨테이너 안에서 `pip freeze > requirements.lock` → 커밋
- Lock 파일 자체는 직접 손으로 편집하지 않음 (생성된 결과물)

---

## 변경 이력

| 날짜 | 변경 | 사유 |
|---|---|---|
| 2026-06-23 | 초안 작성, `requirements.txt` 갱신 적용 | 1차/2차 export 실패 분석 + 환경 재빌드 결정 |
| 2026-06-23 | export 성공 후 `requirements.lock` 생성, Dockerfile 갱신 | Section 5-2 잔여 위험 해소. byte-exact 재현성 확보 |

---

## 작성 정보

| 항목 | 값 |
|---|---|
| 작성일 | 2026-06-23 |
| 작성 시점 진행 단계 | 모델 획득 진행 중, Option B export 1/2차 실패 후 재빌드 직전 |
| 다음 갱신 시점 | 재빌드 후 export 결과 확정 시 |
