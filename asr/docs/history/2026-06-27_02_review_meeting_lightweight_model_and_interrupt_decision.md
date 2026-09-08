# 2026-06-27 — 리뷰 미팅 결정 — 가벼운 ASR 모델 + 인터럽트 지원 (또는 버튼 fallback)

## 시점
2026-06-27 (리뷰 미팅 — 본 작품 마무리 방향)

## 사건
리뷰 미팅에서 본 라인(ASR)에 대한 두 가지 결정:
1. 현재 Whisper Tiny.en TFLite (40 MB)보다 **가벼운 모델**로 교체
2. **인터럽트 가능한 ASR** — 사용자가 발화 중간에 명령 끊을 수 있어야 함
3. 인터럽트 기술적 어려우면 **물리 버튼**으로 fallback

본 라인 v1.x → v2 진입 사이클.

## 1. 현재 v1 상태

| 항목 | 값 |
|---|---|
| 모델 | Whisper Tiny.en TFLite (40 MB, partial int8 DRQ) |
| 측정 | e2e 3.18 s, 6/7 단어 정확, CPU 212%, RSS 357 MB |
| 운영 | 1회 invoke 방식 — 사용자 발화 → 녹음 → invoke → 결과. **인터럽트 없음** |
| 라이선스 | MIT |
| 합격 평가 | 1차 PoC 합격 (4+1 기준) |

## 2. 리뷰 미팅 결정 사항

### 2-1. 가벼운 모델 교체

| 후보 | 크기 | 비고 |
|---|---|---|
| **Whisper Tiny.en (현재)** | 40 MB | DRQ, partial int8 — 더 줄일 여지 |
| Whisper Tiny INT8 (full PTQ) | ~10 MB (추정) | 추가 양자화 — 정확도 영향 검증 필요 |
| Whisper Base 안 함 | — | (Tiny보다 무거움) |
| KWS (Keyword Spotting) | ~1 MB | 명령 단어 몇 개만 — 가장 가벼움. ASR 아님 |
| Picovoice Porcupine / Snowboy | ~수백 KB | 명령 단어 한정 |
| Vosk Tiny | ~50 MB | Whisper 대안, 더 작은 변형 |
| Custom KWS (TFLite micro) | < 1 MB | 명령 5~10개 한정, MCU에서도 동작 |

→ 본 작품 사용처에 따라 결정:
- **자연 발화 인식 필요** (예: "스쿼트 시작해줘") → Whisper 양자화 추가 또는 Vosk
- **명령 단어 한정 OK** (예: "시작", "정지", "다음") → KWS (Picovoice 등)

**KWS 권장** — 본 작품 사용처 (헬스케어 봇 명령) 한정적이라 자연 발화 미필요. 가볍고 빠르고 인터럽트 자연스러움.

### 2-2. 인터럽트 가능한 ASR

| 방식 | 구현 난이도 |
|---|---|
| 스트리밍 ASR (실시간 디코딩) | 어려움 — Whisper는 30초 청크 처리 |
| **KWS 항상 청취** | 쉬움 — 명령 단어 감지 시 즉시 트리거. 인터럽트 본질적 |
| Voice Activity Detection (VAD) | 중간 — 발화 시작/끝 감지 |
| 명령 끝나기 전 중간 결과 stream | 어려움 |

→ **KWS 항상 청취 = 인터럽트 본질적**. Whisper 인터럽트는 모델 자체 한계로 어려움.

### 2-3. Fallback — 물리 버튼

인터럽트 안 되면 사용자가 누르는 **물리 버튼**으로 명령 트리거:
- STM32U585 GPIO 1개로 버튼 입력
- 버튼 press → 녹음 시작 → 발화 → 버튼 release → invoke
- 가장 단순 + 확실

KWS도 못 쓰면 fallback. KWS 잘 동작하면 버튼 불필요.

## 3. 영향

### 3-1. 본 라인 (ASR)
- 모델 교체 → 코드 변경 (Whisper invoke → KWS invoke + 명령 매핑)
- v1 (Whisper) → v2 (KWS) 진입
- 측정 재수행 (KWS 정확도 + latency)

### 3-2. 다른 라인
- Vision 라인 — 무관
- Pose 라인 — 무관 (rep 이벤트는 자체 트리거)
- 본체 (헬스케어 봇) 통합 — 음성 명령 → 모드 전환 / rep 카운트 시작/정지 / 상태 응답 등

### 3-3. 자원 청사진 갱신
- KWS의 CPU/RSS — Whisper 212%/357 MB → 추정 50%/30 MB 정도 (모델 크기 비례)
- 3 라인 동시 운영 부담 ↓ (Vision continuous + KWS 항상 청취 + Pose continuous)

## 4. 다음 단계 (재정렬)

| 우선순위 | 항목 |
|---|---|
| 1 | KWS 후보 모델 비교 (Picovoice Porcupine / TF micro speech / Snowboy) |
| 2 | 명령 단어 set 결정 (예: "시작", "정지", "다음", "카운트", "상태") |
| 3 | KWS TFLite 다운로드 + 호스트 introspection + UNO Q 측정 |
| 4 | KWS 통합 코드 — `infer_microphone_kws.py` |
| 5 | Whisper 코드 보존 (deprecated 표기) — v1 자료 보존 |
| 6 | 본체 음성 명령 → 모드 전환 통합 (헬스케어 봇 + 감시 모드 + 다른 모드) |

## 5. 자료

본 history (리뷰 미팅 결과 ASR 라인 관련).

Pose 라인 동시 결정: [`../../pose/docs/history/2026-06-27_11_review_meeting_outcomes.md`](../../pose/docs/history/2026-06-27_11_review_meeting_outcomes.md)

## 6. 관련

- 직전 ASR history: [`2026-06-27_01_whisper_quantization_actual_form_confirmed.md`](2026-06-27_01_whisper_quantization_actual_form_confirmed.md)
- v1 베이스라인 (Pose 기준): [`../../pose/docs/07_versioning.md`](../../pose/docs/07_versioning.md)
