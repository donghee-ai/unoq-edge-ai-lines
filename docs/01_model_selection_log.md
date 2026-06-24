# 모델 선택 의사결정 로그 - Arduino UNO Q 교감로봇

> 본 문서는 본 프로젝트의 추론 모델 후보들을 검토한 결과와 선택 근거를 시간순으로 기록합니다.
> 모델 획득 단계에서 YOLO 계열을 1차로 진행하며, 후속에 발생할 수 있는 속도 문제에 대비하여 대안 모델을 사전 조사하여 함께 기록합니다.

---

## 결정 요약 (한 화면)

| 항목 | 결정 | 상태 |
|---|---|---|
| 1차 채택 모델 | YOLOv8n int8 (Ultralytics 표준 export 경로) | 진행 중 |
| 전환 트리거 조건 | UNO Q 실측 FPS가 약 **8~10 FPS 미만**일 때 | 측정 대기 |
| 트리거 충족 시 대안 | MediaPipe Face (face_detector + face_landmark) | 사전 조사 완료, 적용 대기 |
| 감정 추론 방식 | L1/L2 규칙 기반 (정규화된 기하 특징, 추론 X) | 모델 선택과 무관, 양쪽 모두 적용 가능 |

---

## 1. 1차 선택: YOLOv8n int8

### 채택 근거

- **Ultralytics 표준 export 워크플로우** 사용
- 본 작품의 기능 요구사항 (사람/얼굴 영역 검출)에 **기능적으로 충분**
- AI Hub 계정 의존 없이 호스트에서 Ultralytics export로 즉시 획득 가능

### 관련 링크

- Ultralytics 공식 문서: <https://docs.ultralytics.com/>
- Qualcomm AI Hub IoT 모델 카탈로그 (참고용): <https://aihub.qualcomm.com/iot/models>
- Qualcomm AI Hub YOLOv8 카드: <https://aihub.qualcomm.com/iot/models/yolov8_det?searchTerm=yolo>

### 알려진 위험 (전환 트리거의 근거)

- QRB2210은 **NPU/HTP 없음**, GPU는 저티어 Adreno 702 (커뮤니티에서 OpenCL 드라이버 이슈 다수 보고)
- 추론은 사실상 **CPU(Cortex-A53 쿼드) + XNNPack 단독 경로**
- 공개 자료 기반 추정치: **3~8 FPS** (320x320 int8 기준)
- 본 작품의 인터랙션 임계점 (~8~10 FPS) 경계선에 위치
- 즉, **기능은 됨, 속도는 측정 후 확정**

### 라이선스

- AGPL-3.0 (Ultralytics 기반)
- 본 작품이 공개 시연/사내 잡지 노출 범위까지는 무관
- 상업 배포 단계로 진입할 경우 Ultralytics 상용 라이선스 또는 대체 모델 검토 필요 (현 단계 범위 외)

---

## 2. 측정 계획 (전환 결정의 근거 데이터)

전환 여부는 추측이 아니라 실측 숫자로 결정합니다.

| 측정 환경 | 측정 항목 | 도구 |
|---|---|---|
| 호스트 도커 (CPU) | 단일 이미지 추론 latency (p50, p95) | TFLite Interpreter benchmark loop |
| UNO Q 디바이스 (CPU) | 비디오 입력 FPS, latency p50/p95 | TFLite Interpreter + benchmark_model |
| UNO Q 디바이스 (GPU 시도) | GPU delegate 동작 여부 | benchmark_model --use_gpu=true |

### 합격선

- **8 FPS 이상**: YOLO 유지, 후속 단계(얼굴 처리) 진행
- **8 FPS 미만**: 다음 절차로 진입
  1. 최적화 1차 (해상도 축소, 스레드 튜닝, frame skipping) 시도
  2. 그래도 미달이면 본 문서 3절의 MediaPipe Face로 전환

---

## 3. 트리거 충족 시 대안: MediaPipe Face

### 정체

- Google MediaPipe의 얼굴 모델 패밀리
- 2개 모델로 구성:
  - `face_detector` (=BlazeFace): 얼굴 bounding box + 6 keypoint
  - `face_landmark_detector` (=FaceMesh): 얼굴 내부 468개 3D landmark

### 도입 사유 (속도 관점에서)

- **얼굴 전용 설계**: 일반 객체 80 클래스를 처리하는 YOLO 대비 모델 규모가 작음
- 모바일 폰의 face filter용으로 설계되어 **CPU 추론에 최적화**
- 따라서 같은 CPU 환경(QRB2210)에서 YOLO보다 빠를 가능성 높음 (단, 실측 필요)

### 부가 이점 (의사결정의 부차 요소)

- 라이선스: Apache-2.0 (배포 자유)
- 이미 TFLite 네이티브 → 추가 변환 단계 불필요
- 468 landmark 출력 → 감정 추론(L1/L2)의 입력으로 직접 사용 가능

### 도입 비용

- 모델 획득: MediaPipe GitHub 또는 pip 패키지에서 직접 (수 분)
- 코드 변경: 전처리/후처리 로직 일부 수정 (예상 수일)
- 학습 비용: BlazeFace landmark 인덱스 및 FaceMesh 468점 매핑표 학습

### 알려진 한계

- Qualcomm AI Hub의 export 대상 칩 목록에 **QRB2210 미지원** 확인 (2026-06 기준)
  → AI Hub 우회, MediaPipe 원본에서 직접 획득 필요
- 공개 벤치마크는 QCS6490 (NPU 보유) 기준으로 503µs / 1988 FPS 표기
  → **QRB2210 (CPU only)에서 50~150x 느려질 것으로 추정**
  → 추정 추론 시간: face_detector 5~25 ms + face_landmark 25~80 ms
  → 합산 10~30 FPS 예상 (실측 필요)

### 관련 링크

- Qualcomm AI Hub MediaPipe Face 모델 카드 (참조 벤치마크 출처): <https://aihub.qualcomm.com/iot/models/mediapipe_face?isQuantized=true>
- MediaPipe 공식 솔루션 문서: <https://ai.google.dev/edge/mediapipe/solutions/guide>
- MediaPipe Python 패키지: <https://pypi.org/project/mediapipe/> (이미지/모델 번들 포함)

### 전환 트리거 충족 전까지의 처리

- 코드 변경 없음, 모델 다운로드 없음
- 본 문서에 사전 조사 내용만 유지
- 트리거 충족 즉시 빠르게 전환 가능하도록 사용 절차 메모만 유지 (별도 문서 작성은 트리거 충족 시점)

---

## 4. 감정 추론 (모델 선택과 무관, 공통 적용)

### 기본 방침: L1/L2 — 추론 신경망 X

- MediaPipe FaceMesh의 468 landmark (또는 YOLO 결과에서 얼굴 crop 후 FaceMesh 별도 호출)
- 정규화된 기하 특징 추출:
  - 기준 단위: 양쪽 눈 사이 거리 (얼굴 회전/거리 무관 정규화)
  - 추출 특징: 미소 비율, 눈꺼풀 거리, 눈썹 높이, 입 열림 정도 등
- 규칙 기반 분류: 5개 감정 (happy / surprised / sad / neutral / drowsy)
- 추가 추론 비용: 사실상 0 (수학 계산만)

### 향후 검토 (L3): 감정 ML 분류기

- L1/L2 실측 정확도가 60~80%로 부족하다고 판단 시
- 후보: FER 계열 작은 CNN (얼굴 crop 입력, ~1 MB, 5~15 ms 추가 비용)
- 본 단계는 현재 검토만, 적용은 트리거 충족 시점에 결정

---

## 변경 이력

| 날짜 | 변경 내용 | 사유 |
|---|---|---|
| 2026-06-23 | 초안 작성 | 1차 모델(YOLO) 채택 + MediaPipe 사전 조사 결과 정리 |
| 2026-06-23 | 관련 링크 추가 | 출처 명시 |
| 2026-06-23 | export 환경 충돌 사고 + 해결 절차는 호스트 환경 정의 문서(00)로 흡수 — 본 문서는 모델 선택 의사결정에만 집중 | 단일 책임 명확화 |

---

## 작성 정보

| 항목 | 값 |
|---|---|
| 작성일 | 2026-06-23 |
| 작성 시점 진행 단계 | 환경 셋업 완료, 모델 획득 단계 진입 |
| 본 문서의 다음 갱신 시점 | 호스트/디바이스 실측 FPS 수치 확보 후 |
