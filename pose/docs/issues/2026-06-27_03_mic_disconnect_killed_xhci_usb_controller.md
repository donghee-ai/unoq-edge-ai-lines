# 2026-06-27 — 마이크 USB 분리 시 xhci-hcd USB host controller 전체 deregister

## 증상

SSH 모드 운영 중 사용자가 **마이크 USB 케이블만 뽑았는데** 카메라도 함께 사라짐. `infer_camera_pose.py` 실행 시:

```
[ WARN ] global cap_v4l.cpp:914 open VIDEOIO(V4L2:/dev/video0): can't open camera by index
ERROR: cannot open camera /dev/video0
```

## 진단

```bash
ls /dev/video*           # → /dev/video2, /dev/video3 만 (Venus codec)
v4l2-ctl --list-devices  # → Qualcomm Venus decoder + encoder 만
lsusb | grep ...         # → 빈 결과 (USB device 전체 미인식)
```

**dmesg 결정적**:
```
[128.472] xhci-hcd xhci-hcd.2.auto: remove           ← USB controller 자체 제거
[128.495] usb 2-1: USB disconnect
[128.503] r8152-cfgselector: USB disconnect          ← Realtek 이더넷 disconnect
[128.515] r8152: Stop submitting intr, status -108
[128.626] xhci-hcd xhci-hcd.2.auto: USB bus 2 deregistered
[128.643] usb usb1: USB disconnect
[128.648] uvcvideo 1-1.2:1.1: Failed to resubmit video URB (-19)
[128.671] usb 1-1: USB disconnect
[128.689] usb 1-1.1: USB disconnect
[128.765] usb 1-1.2: USB disconnect                  ← UVC 카메라 disconnect
[128.832] xhci-hcd xhci-hcd.2.auto: USB bus 1 deregistered  ← USB bus 1 자체 제거
```

→ 마이크만 분리한 게 아니라 **xhci-hcd USB host controller(USB bus 1, 2) 전체가 deregister됨**. 결과적으로 그 위에 있던 모든 USB device(카메라/마이크/이더넷)가 한꺼번에 사라짐.

`/dev/video2,3`은 Qualcomm SoC 내장 비디오 코덱(Venus)이라 USB 무관 → 그대로 남음.

## 원인 (추정)

마이크 케이블 뽑는 물리적 동작이 다음 중 하나를 유발:
1. UNO Q ↔ 허브 USB-C 케이블이 살짝 빠짐
2. 허브 자체 power/PD 상태 변동으로 xhci enumeration 재시작 실패
3. USB-C PD power role 협상 중 driver state 깨짐

UNO Q USB-C 1포트 한계 + 허브 의존 토폴로지의 약점. session summary의 USB 토폴로지 결정 모드에서 SSH 모드(허브+카메라+마이크) 운영 시 잠재 함정.

## 해결

```bash
# 1. lsusb 확인 (host controller 죽음 확정)
lsusb

# 2. UNO Q ↔ 허브 USB-C 케이블 분리 → 3초 → 재연결
#    (마이크/카메라 케이블 X, UNO Q 본체 케이블)

# 3. 5초 기다린 다음 확인
sleep 5
ls /dev/video*
lsusb
v4l2-ctl --list-devices

# 4. 그래도 복구 안 되면 reboot (가장 확실)
sudo reboot
```

`modprobe uvcvideo`만으로는 **불충분** — xhci-hcd가 deregister된 상태에선 USB 물리 layer 자체가 작동 안 함.

기대 정상 상태:
```
/dev/video0       uvcvideo (SU200 UVC)
/dev/video1       uvcvideo (SU200 metadata 노드, 기종마다)
/dev/video2,3     Qualcomm Venus decoder/encoder
```

## 재발 방지

- **카메라/마이크 USB 분리·재연결은 가급적 UNO Q 전원 OFF 상태에서**
- 운영 중 USB device 교체 필요 시: **항상 dmesg tail로 host controller 상태 먼저 확인**
- USB-C 케이블 (UNO Q ↔ 허브) 잘 끼워졌는지 압력 점검 (살짝 흔들리면 PD 영향)
- 향후 안정 토폴로지: 외장 powered USB hub + UNO Q 별도 전원 (PD 의존 줄임)

## 영향

- 본 사이클 실측 중단 (스쿼트 카운터 검증 보류)
- 복구 후 동일 명령으로 재시도 필요

## 관련

- USB 토폴로지 결정: [`../../vision/docs/history/2026-06-25_03_usb_topology_decision.md`](../../vision/docs/history/2026-06-25_03_usb_topology_decision.md)
- 카메라 노드 함정 (Venus vs UVC): vision 라인 SESSION_SUMMARY_2026-06-24 §1-8
