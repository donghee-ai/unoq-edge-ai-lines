# Issues — vision 라인 이슈/문제/오류/함정 실시간 기록

본 작품 vision 라인 (YOLO + 카메라 + 향후 fusion) 진행 중 발생한 **문제 / 오류 / 의외 동작 / 함정**의 발견·진단·해결을 실시간 기록.

## 파일명 규칙

```
<YYYY-MM-DD>_<NN>_<짧은_제목>.md
```

| 부분 | 형식 | 예시 |
|---|---|---|
| 날짜 | `YYYY-MM-DD` (ISO 8601) | `2026-06-25` |
| 일련번호 | 그날의 순번 (`01`, `02`, …) | `01` |
| 짧은 제목 | 영문 lowercase + underscore (어떤 이슈인지 즉시 알게) | `camera_uvc_unbind`, `thermal_throttle_observed`, `yolo_export_autoupdate` |

전체 예시:
- `2026-06-25_01_camera_uvc_unbind.md`
- `2026-06-25_02_thermal_70deg_in_285s.md`
- `2026-07-03_01_monorepo_link_broken.md`

→ 파일명만 봐도 **언제 + 어떤 이슈** 즉시 파악 가능.

## 작성 형식 (1 이슈 1 파일)

```markdown
# <한 줄 제목>

## 증상
- 어떤 명령/작업 중 발생했는가
- 출력 메시지 / 스택트레이스 (그대로 복사)

## 원인
진단 결과

## 해결
어떤 명령 / 코드 수정으로 해결됐는가

## 재발 방지
향후 같은 함정 회피 방법 (사전 점검 / 코드 패턴 / 환경 설정)

## 관련
- 관련 issues / history / docs 파일 링크 (선택)
```

## 기록 시점

**일이 생기는 즉시**:
- Python 오류 / 명령 실패 / 의외 동작 발견
- 환경 차이 / 호환 문제 발견
- 시간 잡아먹은 함정 해결 후

**배치 금지** — 한꺼번에 몰아 기록 X. 발견 즉시 1 파일.

## 기존 함정 (이미 docs/에 기록된 것)

vision 라인 1차 PoC 진행 중 발견된 함정들은 이미 docs/에 정리됨:

| 함정 | 기록 위치 |
|---|---|
| Ultralytics AutoUpdate가 핀된 환경 침범 | [`../docs/01_host_environment_setup.md`](../docs/01_host_environment_setup.md) §10 |
| torch numpy ABI 묶임 | 동상 |
| 호스트명 ≠ SSH 사용자명 (`unoq-korea01` vs `arduino`) | [`../docs/04_device_setup.md`](../docs/04_device_setup.md) §1 |
| 한/영 IME 함정 (비번 입력) | 동상 |
| TFLite 런타임 / cv2 사전 설치 X | [`../docs/04_device_setup.md`](../docs/04_device_setup.md) §6 |
| Ultralytics int8 TFLite 정규화 좌표 [0,1] | [`../docs/06_postprocess_and_e2e.md`](../docs/06_postprocess_and_e2e.md) §3 |
| cv2 drawing cold start ~60 ms | [`../docs/06_postprocess_and_e2e.md`](../docs/06_postprocess_and_e2e.md) §4 |
| 카메라 USB 인식 / uvcvideo 재로드 | [`../docs/08_realtime_camera.md`](../docs/08_realtime_camera.md) §7-5 |
| nested SSH (디바이스 안에서 또 ssh) | 동상 |
| thermal 285초에 70.8°C (합격선 1°C 초과) | [`../docs/08_realtime_camera.md`](../docs/08_realtime_camera.md) §3-3 |

→ 본 폴더는 **향후 발생** 신규 이슈 전용. 기존 함정은 위 docs/ 그대로 참조.

## 관련 자산
- [`../history/`](../history/) — 의사결정 / 마일스톤 / 진행 사항
- [`../docs/`](../docs/) — 1차 PoC 통합 정리 (00~09 + improvement)
- [`../SESSION_SUMMARY_*.md`](../) — 세션 종료 핸드오프
