# Preflight Notes — ASR 작업 시작 전 알아둘 점

본 문서는 `unoq-asr` 모듈 작업에 진입하기 전 반드시 숙지해야 할 환경 제약, 코드 규약, 라이선스 원칙, vision 라인에서 발견한 함정의 ASR 적용, 보고 시 표현 규약, 사전 게이트 체크리스트를 한곳에 모은 것입니다. 본문 작업(02~) 시작 전 1회 정독 권장.

## 0. 핵심 결정 (요약)

| 항목 | 내용 |
|---|---|
| **타겟** | UNO Q (QRB2210, Cortex-A53 ×4, CPU 단독, AI 가속기 없음) |
| **런타임** | `ai-edge-litert` (TFLite / LiteRT) — QAIRT·SNPE·QNN 미지원 |
| **모델 (1차)** | Google Speech Commands v2 TFLite (KWS, ~300 KB, Apache-2.0) |
| **언어** | 영어 35단어 1차, 한국어 fine-tune 2차 |
| **호스트 환경** | WSL2 + Docker `asr-dev` 별도 컨테이너 (vision-dev와 분리) |
| **디바이스 환경** | `~/venv-unoq` 통합 venv (vision + audio 의존성 공존) |
| **합격선** | latency mean ≤ 50 ms / p95 ≤ 80 ms / RSS < 100 MB / temp ≤ 70°C / accuracy ≥ 80% |
| **상업 라이선스** | Apache-2.0 / MIT / BSD만. AGPL · GPL · CC-NC · 상용(Picovoice) 차단 |

## 1. 환경 제약 — UNO Q 디바이스

| 항목 | 값 / 제약 |
|---|---|
| SoC | QRB2210 (DSP / HTP / NPU 없음 → **CPU 단독**) |
| CPU | Cortex-A53 ×4 @ 2.0 GHz (In-Order, 작은 SIMD) |
| RAM | 4 GB (가용 2.4 GiB) |
| **eMMC 가용** | **2.9 GB (이미 69% 사용 — 좁음)** |
| OS | Debian aarch64 (kernel 7.0) |
| Python | 3.13.5 (시스템) |
| venv | `~/venv-unoq` (vision과 공유) |
| App root | `/opt/unoq-yolo/{models,labels,media,configs,logs}` (현재 vision 명칭 — 향후 monorepo 통합 시 rename 검토) |
| SSH | `arduino@192.168.0.45` (한/영 IME 영어 모드 점검) |
| 마이크 | USB Audio Class 보유, 인식 미점검 |

핵심:
- **AI 가속기 0 → 30 FPS 같은 hard requirement 잡지 않음**. KWS는 CPU 4 thread XNNPACK으로 충분
- **디스크 좁음 → venv 분리 비추** (이미 청사진 §8-3에서 결정)
- **마이크 인식 점검 필수** (vision 카메라처럼 사전 검증 없이 진입하면 무한 디버깅)

## 2. 호스트 환경 제약

| 항목 | 값 |
|---|---|
| Windows 11 + WSL2 (Ubuntu 24.04) | vision과 동일 |
| Docker | `asr-dev` 별도 컨테이너 (vision-dev와 분리) |
| Python (컨테이너) | 3.10 (예정 — vision과 동일 버전) |
| AI 런타임 (컨테이너) | `ai-edge-litert` + (필요 시) tensorflow |
| Audio 의존성 | `librosa`, `sounddevice`, `scipy` |
| 디스크 여유 | ~3 GB (이미지 + 패키지 + 모델) |

## 3. 코드 규약 — vision 라인에서 채택, 본 모듈도 동일

### 3-1. 추론 코드 패턴 (필수 준수)

| 규약 | 내용 |
|---|---|
| **q-offset / q-scale hard-code 금지** | `interpreter.get_input_details()`로 자동 추출 |
| **3단 import 폴백** | `ai_edge_litert.interpreter` → `tflite_runtime.interpreter` → `tensorflow.lite` |
| **dtype 분기** | float32 / uint8 / int8 입력 변환 명시적 분기 |
| **GPU delegate optional** | 본 작품 CPU 단독, GPU는 flag로만 enable + fail-safe fallback (silent X) |
| **latency p50 / p95 + warmup 분리** | 첫 N회는 warmup, 그 후 measure |
| **모델 메타데이터 자동 검증** | shape / dtype / quantization 로드 후 확인 |

### 3-2. 후처리 분리 패턴

vision의 `src/postprocess.py` 패턴을 audio에도 적용:

1. dequantize (필요 시)
2. reshape / transpose
3. confidence threshold
4. class filter
5. (vision: coordinate scaling / audio: softmax + top-1)
6. NMS (vision만)
7. class label mapping

audio 모듈 예정:
- `src/preprocess.py` (MFCC / log-Mel)
- `src/postprocess.py` (softmax + top-1 + threshold + label)
- `src/audio_io.py` (sounddevice 래퍼)

## 4. 측정 / 벤치마크 표준

### 4-1. JSON 형식 (벤치마크 표준 권고 그대로)

```json
{
  "model": "...",
  "runtime": "ai_edge_litert:4",
  "input_shape": [1, 49, 40, 1],
  "frames": 100,
  "latency_ms_p50": 0.0,
  "latency_ms_p95": 0.0,
  "fps_mean": 0.0,
  "preprocess_ms_mean": 0.0,
  "postprocess_ms_mean": 0.0,
  "dropped_frames": 0,
  "max_rss_mb": 0,
  "max_temp_c": 0
}
```

audio 확장 필드: `capture_ms_mean`, `accuracy_top1`, `accuracy_top5`, `false_positive_rate`.

### 4-2. 측정 패턴

| 단계 | 도구 | 출력 |
|---|---|---|
| 1. 모델 검증 (단발) | `validate_kws.py` | input/output shape, dtype, quantization 자동 출력 |
| 2. Latency 측정 (50회) | `validate_kws.py --runs 50 --warmup 5` | mean / p50 / p95 / FPS |
| 3. 실시간 마이크 (무한 루프) | `infer_mic.py` | 라벨 + confidence 콘솔 출력 |
| 4. 공식 벤치 (100회) | `benchmark_kws.py --runs 100 --warmup 10 --json ...` | 벤치마크 표준 JSON |

### 4-3. 합격선 4 + 1 기준

| 기준 | 임계값 | 측정 도구 |
|---|---|---|
| Latency mean | ≤ 50 ms | validate_kws.py |
| Latency p95 | ≤ 80 ms | validate_kws.py |
| Max RSS | < 100 MB | `/proc/self/status` VmRSS |
| Max temp | ≤ 70°C | `/sys/class/thermal/thermal_zone*/temp` |
| Accuracy top-1 (참고) | ≥ 80% | golden wav set |

## 5. 라이선스 원칙 (상업 배포 가능 기준)

### 5-1. 3중 점검 (모델 + 데이터 + 코드)

| 계층 | 1차 선택 | 라이선스 |
|---|---|---|
| **모델 가중치** | Google Speech Commands v2 | Apache-2.0 |
| **학습 데이터** | Speech Commands v2 발화 (~106k) | CC BY 4.0 |
| **본인 코드** | 본 모듈 src | (Public 전환 시) Apache-2.0 권장 |
| **의존 패키지** | librosa, sounddevice, scipy, numpy | BSD / Apache 계열 |

### 5-2. OK 라이선스 (상업 배포 자유)

`Apache-2.0` / `MIT` / `BSD-2/3-Clause` / `ISC` / `CC0` / `CC BY 4.0`(데이터)

### 5-3. 차단 라이선스

| 라이선스 | 이유 |
|---|---|
| `AGPL-3.0` (YOLOv8) | 네트워크 사용도 소스 공개 의무 — vision 라인에서도 향후 교체 검토 중 |
| `GPL-3.0` (YOLOv7) | 결합 프로젝트 소스 공개 의무 |
| `CC BY-NC` | NonCommercial — 상업 금지 |
| `상용` (Picovoice Porcupine) | 별도 라이선스 구매 필요 |
| `Custom / "research only"` | 명시 허가 없으면 사용 불가 |

### 5-4. 조건부

| 라이선스 | 조건 |
|---|---|
| `MPL-2.0` (Coqui STT) | 수정한 파일만 공개 (전체 프로젝트는 X) — 분리 관리 시 OK |
| `LGPL` | 동적 링크 OK, 정적 결합은 GPL 전염 위험 |

## 6. 참고자료 대외비 원칙

| 규칙 | 내용 |
|---|---|
| 인용 금지 | 외부 참고자료 원본의 파일명 · 섹션번호 · JIRA · CR 번호 절대 표기 X |
| 한국어 번역본 위치 | `vision/docs/_private_refs/` (vision 라인에만 보관, `.gitignore` 처리) |
| 본 `unoq-asr` 폴더 | **참고자료 폴더 없음** — 참고 가이드는 vision 라인에서 인용 |
| 본인 docs 인용 시 | "환경 변수 표준화", "벤치마크 JSON 형식" 같은 일반 원칙으로만 |
| Public 전환 시 | 참고자료 흔적(`setenforce 0` 같은) 재점검 + redact |

## 7. vision 라인 함정의 ASR 적용

vision 작업에서 발견한 8개 함정 중 ASR에 재발 가능한 패턴:

| vision 함정 | ASR 재발 가능성 | 대응 |
|---|---|---|
| Ultralytics AutoUpdate가 핀 침범 | 낮음 (Ultralytics 안 씀) | requirements-asr.lock 사전 핀 |
| torch numpy ABI 묶임 (torch 2.1.x ↔ numpy <2) | 중간 (torch 미사용이지만 numpy 메이저 확인) | librosa의 numpy 호환 점검 |
| 호스트명 ≠ SSH 사용자명 | 동일 — `arduino@192.168.0.45` 그대로 | 변경 없음 |
| 한/영 IME 영어 모드 점검 | 동일 | 비번 입력 전 확인 |
| TFLite 런타임 사전 설치 X | 동일 — vision 셋업으로 이미 해결 | venv-unoq 그대로 활용 |
| cv2 사전 설치 X | 동일 — `opencv-python-headless` 이미 설치 | 그대로 |
| **Ultralytics int8 TFLite 정규화 좌표 [0,1]** | **유사 패턴 — audio 입력 정규화 함정** | 모델 input dtype + 범위 사전 확인 ([-1, 1] vs [-32768, 32767] vs uint8 0~255) |
| **cv2 drawing cold start ~60 ms** | **유사 패턴 — sounddevice / librosa 첫 호출 비용** | warmup 분리 측정 + 첫 호출 outlier 처리 |

→ vision 함정 docs (vision `docs/00` 등)에서 학습한 패턴이 ASR에도 그대로 적용. **새 라이브러리(sounddevice, librosa) 첫 호출 비용 측정 필수**.

## 8. 디바이스 측 표준 (vision과 공유)

| 자산 | 위치 / 이름 | 비고 |
|---|---|---|
| venv | `~/venv-unoq` | 통합 — audio 의존성 `pip install` 추가만 |
| 모델 | `/opt/unoq-yolo/models/` (audio 모델은 서브폴더 `audio/` 또는 평탄 둘 다 가능 — 결정 보류) | 향후 monorepo 시점에 `/opt/unoq-companion/models/audio/` 검토 |
| 라벨 | `/opt/unoq-yolo/labels/labels_35.txt` | audio용 신규 |
| 미디어 (디버그 wav) | `/tmp/unoq-yolo/audio-debug/` | 일시 작업 (`/opt`에 두지 말 것) |
| 벤치 결과 | `~/benchmarks/` + 호스트 회수 | JSON 파일명: `device_kws_<YYYYMMDD>.json` |
| 로그 | `/opt/unoq-yolo/logs/` | JSON lines |

### 8-1. 디바이스 의존성 추가 (1회)

```bash
ssh arduino@192.168.0.45
source ~/venv-unoq/bin/activate
pip install sounddevice scipy librosa
# numpy 메이저 충돌 발생 시 그때 분리 결정
```

### 8-2. 디스크 점검

```bash
df -h /
# 가용 ≥ 1 GB 확인. 부족 시 /tmp 정리 또는 모델 변종 삭제
```

## 9. 보안 / 개인정보 (ASR 특화)

| 항목 | 정책 |
|---|---|
| 마이크 raw wav 저장 | **기본 off** (영상 정책과 동일) |
| 디버그 wav 저장 | `--save-dir` opt-in (`/tmp/unoq-yolo/audio-debug/`) |
| 클라우드 음성 인식 | 사용 안 함 (local inference only) |
| 자유발화 보호 | 본 1차 모듈은 KWS (35단어 N-gram이 아니라 단어 분류) → 자유발화 캡쳐 X → 개인정보 영향 작음 |
| 로그 | JSON lines, raw audio tensor 저장 default off |
| secrets | `${APP_ROOT}/configs/secrets.env` 권한 600 |
| 영상 + 음성 동시 운영 시 | Privacy 정책 결합 — debug frame + debug wav 모두 opt-in |

## 10. 보고 시 표현 규약

### 10-1. 단정적 표현 지양

| 권장 X | 권장 O |
|---|---|
| "AI Hub에서 다운로드함" | "Speech Commands v2 사전학습 모델을 TF Hub / Google AI Edge에서 획득 — Apache-2.0 라이선스 확인" |
| "GPU delegate 사용" | "CPU 단독(XNNPACK) 경로 — `/dev/kgsl*` 부재로 GPU delegate 후순위" |
| "30 FPS 달성" | "8~15 FPS 목표 (CPU 4 thread 기준, 30 FPS는 hard requirement 아님)" |
| "정확도 95%" | "본인 발화 N건 기준 top-1 정확도 X% (영어 35단어, 외부 데이터셋 미검증)" |

### 10-2. 의사결정 흐름 명시

- 왜 KWS? — 요구사항 "음성으로 조정" 의도 + 작은 모델 + 자유발화 불필요
- 왜 Speech Commands v2? — 3중 라이선스 클린 + TFLite 즉시 사용 + 0.3 MB
- 왜 영어 1차? — 사전학습 즉시 사용, 한국어는 fine-tune 작업 분리
- 왜 ai-edge-litert? — vision과 같은 런타임 일관성

### 10-3. 사실 / 추측 분리 (`docs/03 §7-4` 패턴)

- **검증**: "본 환경에서 50회 측정 mean X ms 확인"
- **인용**: "[Apache-2.0 라이선스 표기]에 따르면 ..."
- **추측**: "...일 가능성 높음 (실측 필요)"

## 11. 작업 시작 전 사전 게이트 체크리스트

본문 작업(02~) 진입 전 다음 항목 모두 확인:

### 11-1. 호스트

- [ ] WSL2 동작 (`wsl -l -v` → Ubuntu STATE=Running)
- [ ] Docker Desktop 또는 Docker Engine running (`docker --version`)
- [ ] 작업 폴더 `c:\Project\asr\` 존재 (이미 생성됨)
- [ ] git 관리 결정 보류 사항 인지 (별도 repo? unoq-companion-robot fork? unmanaged?)
- [ ] 디스크 여유 ~3 GB (호스트 측 Docker 이미지 빌드용)

### 11-2. 디바이스

- [ ] `ssh arduino@192.168.0.45` 접속 가능 (한/영 영어 모드)
- [ ] `~/venv-unoq` 활성화 성공 (`source ~/venv-unoq/bin/activate`)
- [ ] 기존 vision import 동작 (`python3 -c "from ai_edge_litert.interpreter import Interpreter"`)
- [ ] USB 마이크 인식 (`arecord -l` → 카드 표시)
- [ ] ALSA 인식 (`cat /proc/asound/cards` → 마이크 항목)
- [ ] 디바이스 디스크 가용 ≥ 1 GB (`df -h /`)
- [ ] 디바이스 시간 동기화 (벤치 JSON 타임스탬프용)

### 11-3. 보고용 환경

- [ ] 본 청사진(`00`) + preflight(`01`) 1회 정독
- [ ] vision 합격 측정 자산(9.23 FPS) 보존 확인 (`vision/benchmarks/` 그대로)
- [ ] 라이선스 원칙 5절 숙지
- [ ] 참고자료 대외비 원칙 6절 숙지

## 12. 작업 시작 후 첫 게이트 (호스트 단계)

| # | 게이트 | 통과 기준 |
|---|---|---|
| 1 | Docker `asr-dev` 빌드 성공 | `bash docker/run-asr.sh` → 컨테이너 진입 |
| 2 | Smoke test (컨테이너 안) | `python -c "import librosa, sounddevice, ai_edge_litert; print('OK')"` |
| 3 | KWS 모델 다운로드 + 검증 | `interpreter.allocate_tensors()` 성공 + shape 자동 출력 |
| 4 | 모델 input/output shape 확정 | 청사진 §4-1 예상값과 비교 |
| 5 | 호스트 첫 inference (랜덤 입력) | `interpreter.invoke()` 성공 + output shape 확인 |
| 6 | 호스트 baseline latency 50회 | mean / p50 / p95 출력 |

## 13. 디바이스 단계 첫 게이트

| # | 게이트 | 통과 기준 |
|---|---|---|
| 1 | 모델 전송 | `scp ...` → 디바이스 `/opt/unoq-yolo/models/` |
| 2 | 디바이스 audio 의존성 설치 | `pip install sounddevice scipy librosa` 성공 |
| 3 | 디바이스 첫 inference | `python3 ~/validate_kws.py ...` → invoke 성공 |
| 4 | 디바이스 latency 50회 측정 | mean ≤ 50 ms 기대 (합격선) |
| 5 | 마이크 캡쳐 1초 PCM | `sounddevice.rec(...)` → 16 kHz int16 또는 float32 |
| 6 | 실시간 KWS 단어 인식 | "yes" 또는 "stop" 발화 → 콘솔 라벨 출력 |

## 14. 결정 보류 사항 (향후 별도 의사결정)

| 항목 | 결정 시점 |
|---|---|
| numpy 메이저 호환성 (vision 2.5.0 + librosa 호환 여부) | `03_host_env_setup.md` 빌드 단계 실측 |
| 디바이스 측 audio 모델 경로 (`/opt/unoq-yolo/models/audio/` 신설 vs 평탄) | 첫 전송 직전 |
| git 관리 (별도 repo / unoq-companion-robot fork / unmanaged) | preflight 정독 후 즉시 |
| 한국어 명령 fine-tune 시점 | 영어 1차 합격 + 리뷰 피드백 후 |
| MCU(STM32U585) 통신 프로토콜 | fusion 단계 |
| `docs/00 §6 후속 문서 번호 재배치` (본 파일 끼어들어 1씩 밀림) | 청사진 §6 갱신 시 같이 처리 |

## 15. 본 파일의 위치 / 청사진과의 관계

- 청사진(`00`) = "왜 / 무엇을" (전략·청사진·합격선)
- preflight(`01`, 본 파일) = "주의·전제·규약·체크리스트" (작업 진입 직전 1회 정독)
- 본문(`02~07`) = "어떻게" (실제 작업 절차)

청사진 §6 후속 문서 매핑은 본 preflight 끼어들어 1씩 밀린 상태로 갱신 — `00_project_blueprint.md` §6 표 참조.

## 한 줄 요약

> **CPU 단독 + ai-edge-litert + Speech Commands v2 (Apache-2.0) + 영어 1차 + 디바이스 venv 통합 + 벤치마크 표준 JSON 합격선 4기준 + vision 함정 8개 중 audio 재발 패턴 2개(라이브러리 cold start / 입력 정규화 범위) + 라이선스 3중 점검 — 13개 사전 게이트 통과 후 본문 작업 진입.**
