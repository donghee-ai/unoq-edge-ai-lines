# 밟은 함정 — 증상에서 원인으로

여기 있는 건 전부 **직접 밟고 시간을 쓴 것**들입니다. 라인별 `issues/`에 흩어져 있던
것을 증상 기준으로 모았고, 각 항목의 상세 경위는 원본 파일로 넘깁니다.

## 0. 증상에서 시작하기

| 증상 | 원인 | 절 |
|---|---|---|
| "ONNX 모델"인데 로드가 안 된다 | 사전 컴파일된 QNN 바이너리 — 다른 칩 전용 | §1 |
| 허브를 끼우면 ADB가 안 잡힌다 | USB-C 케이블이 충전 전용 | §2 |
| 마이크 뽑았더니 USB가 통째로 죽었다 | xhci 컨트롤러 deregister | §3 |
| 오래 돌리면 온도가 합격선을 넘는다 | 지속 부하 thermal plateau | §4 |
| 측면·후면 자세에서 검출이 뚝 떨어진다 | 카메라가 너무 낮다 | §5 |
| PowerShell로 이름 바꿨더니 빈 폴더가 남았다 | rename 중 점유 / NTFS 스트림 표기 | §6 |

## 1. Qualcomm AI Hub 모델은 다른 칩 전용이다

**증상** — `mediapipe_pose-precompiled_qnn_onnx-w8a8-...x2_elite.zip`을 받아 로드하면
`Unsupported model IR version: 13, max supported IR version: 10`.

**원인** — ONNX 모델이 아니라 **사전 컴파일된 QNN 컨텍스트 바이너리를 ONNX로 포장한
것**이다. `EPContext` 노드 + `EPContext.source = QNN`이 증거이고, 실제 연산은 컴파일
대상 칩(Snapdragon X2 Elite)에서만 돈다. IR 버전을 맞춰도 QRB2210에서는 소용없다.

**대응** — TFLite + `ai-edge-litert` 스택으로 확정. 이 판단이 네 라인 전체의 기반이 됐다.

**재발 방지** — 모델을 받기 전에 **대상 칩**과 `EPContext` 유무를 확인할 것. 파일
확장자가 `.onnx`라고 이식 가능한 게 아니다.

→ 원문: [`pose/docs/issues/2026-06-27_01`](../pose/docs/issues/2026-06-27_01_precompiled_qnn_onnx_incompatible_with_qrb2210.md)
· 배경: [`03_model_choice.md`](03_model_choice.md) §4

## 2. 허브 경유 ADB — 범인은 케이블이었다

**증상** — 허브를 거치면 ADB에 디바이스가 안 뜨거나, 뜨더라도 **"Billboard Device"
(VID 2f61)만** 등록된다.

**원인** — Billboard Device는 USB-C **Power Delivery 협상 시 등록되는 메타 장치**로,
실제 데이터 인터페이스가 없다는 신호다. 확률 순으로 ① **USB-C 케이블이 충전 전용**
(생김새가 같아도 D+/D− 핀이 없다) ② 허브 데이터 패스가 alt mode로 빠짐 ③ 허브 전력 부족.

**대응** — 데이터 지원 케이블로 교체 + 직결. 이후 SSH 기반 작업으로 전환해 ADB 의존을
줄였다.

**재발 방지** — "Billboard Device만 보인다"는 **케이블을 먼저 의심하라는 신호**다.
허브·포트·드라이버를 뒤지기 전에 케이블부터 바꿔볼 것.

→ 원문: [`vision/docs/issues/2026-06-25_01`](../vision/docs/issues/2026-06-25_01_adb_lost_when_through_hub.md)
· [`_02`](../vision/docs/issues/2026-06-25_02_adb_billboard_device_only_via_hub.md)

## 3. 마이크를 뽑자 USB 컨트롤러 전체가 죽었다

**증상** — 마이크 USB를 분리하는 순간 `xhci-hcd` USB host controller가 통째로
deregister. 카메라까지 같이 사라진다.

**원인(추정)** — 케이블 분리 동작이 ① UNO Q↔허브 USB-C 접점을 흔들었거나 ② 허브 PD
상태 변동으로 xhci enumeration 재시작이 실패했거나 ③ PD power role 협상 중 드라이버
상태가 깨진 것. **UNO Q의 USB-C 1포트 + 허브 의존 토폴로지의 구조적 약점**이다.

**재발 방지** — 구동 중에는 USB를 뽑지 말 것. 뽑아야 하면 프로세스를 먼저 내린다.

→ 원문: [`pose/docs/issues/2026-06-27_03`](../pose/docs/issues/2026-06-27_03_mic_disconnect_killed_xhci_usb_controller.md)

## 4. thermal은 합격선에 여유가 없다

**증상** — 136초 측정에서는 68.6 °C(합격)였는데, **지속 구동에서 71.4 °C plateau**로
합격선 70 °C를 1.4 °C 넘겼다.

**원인(추정)** — A53 4코어 78 % 사용 누적 발열 + MJPEG 서빙(JPEG 인코딩 + 소켓 I/O)
추가 부하. UNO Q는 **passive 방열만** 한다.

**상태** — 미해결. **soak(장시간) 측정을 아직 안 했다.** 짧은 측정만으로 thermal을
판정하면 안 된다는 것이 이 항목의 핵심이다.

→ 원문: [`pose/docs/issues/2026-06-27_04`](../pose/docs/issues/2026-06-27_04_thermal_plateau_71c_exceeds_70_margin.md)

## 5. 카메라 높이가 검출률을 지배한다

**증상** — 정면 자세는 잘 잡히는데 **측면·후면에서 keypoint 검출률이 급락**한다.

**원인** — 카메라가 바닥 근처에 있어 **수직 화각이 부족**하다. hip/knee/ankle이 원근
왜곡으로 정상 비례를 벗어나고, 측면에서는 한쪽 다리 occlusion + 신체 일부가 프레임
밖으로, 후면에서는 nose/eyes/shoulders가 안 보여 MoveNet 전체 신뢰도가 떨어진다.

**측정 근거** — 정면은 L·R 둘 다 ~170°(Standing) / 90° 이하(Squat)로 명확히 갈리는데,
측면·후면 구간에서는 한쪽이 미검출(`?`)로 빠진다.

**대응** — 카메라를 높이거나 사람이 더 뒤로. 알고리즘으로 해결할 문제가 아니다.

→ 원문: [`pose/docs/issues/2026-06-27_05`](../pose/docs/issues/2026-06-27_05_camera_low_position_side_back_detection_drop.md)

## 6. PowerShell `Rename-Item`이 빈 폴더를 남겼다

**증상** — 폴더 이름 변경 후 `unoq-mediapipe-pose;C` 같은 빈 폴더가 잔류.

**원인(추정)** — 대상이 다른 프로세스(VSCode·탐색기)에 점유돼 atomic rename이 부분만
처리됐거나, NTFS alternate data stream 표기(`파일명:스트림:타입`)가 잘못 쓰인 것.

**대응** — 내용이 없음을 확인하고 삭제. 원인 확정보다 정리가 우선이었다.

**참고** — 이 함정은 **다시 재현됐다.** 2026-09-08 리포 폴더명 변경 시 VSCode 파일
감시자가 디렉토리 핸들을 잡아 `Device or resource busy` → `Access denied`로 막혔다.
**워크스페이스로 열려 있는 폴더는 이름을 못 바꾼다** — 에디터를 닫고 해야 한다.

→ 원문: [`pose/docs/issues/2026-06-27_02`](../pose/docs/issues/2026-06-27_02_powershell_rename_item_created_stray_empty_folder.md)

## 7. 기록 규칙

새 함정을 밟으면 **해당 라인의 `docs/issues/`에 한 사건 한 파일**로 먼저 쓰고
(`YYYY-MM-DD_NN_주제.md`), 재사용 가치가 있다고 판단되면 이 문서 §0 표에 한 줄 추가한다.
이 문서는 색인이고, 원본은 고치지 않는다.
