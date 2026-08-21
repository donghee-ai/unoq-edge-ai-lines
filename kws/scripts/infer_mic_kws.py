#!/usr/bin/env python3
"""실시간 마이크 → KWS → top-1 라벨 출력 (KWS 단독 검증용).

pose 통합 이전 KWS worker 만 격리 검증. Ctrl+C 로 종료 + SUMMARY.

사용:
  # 디바이스 (SSH 접속 후):
  source ~/venv-unoq/bin/activate
  python3 ~/kws_test/scripts/infer_mic_kws.py \
      ~/kws_test/models/kws_ref_model_ds_cnn_int8.tflite \
      ~/kws_test/scripts/labels_12.txt \
      --preset ds_cnn \
      --print-every 5

  # confidence threshold 조정 + 다른 입력 장치:
  python3 infer_mic_kws.py model.tflite labels_12.txt \
      --preset ds_cnn --conf 0.6 --device 2
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

# 같은 폴더 모듈 import
sys.path.insert(0, str(Path(__file__).resolve().parent))

from kws_worker import KWSWorker
from mode_controller import Mode, ModeBus


def _list_devices():
    try:
        import sounddevice as sd
        print(sd.query_devices())
    except Exception as e:
        print(f"[list-devices] error: {e}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("model", nargs="?", help="KWS TFLite 모델 경로 (--list-devices 시 생략)")
    ap.add_argument("labels", nargs="?", help="labels_*.txt (--list-devices 시 생략)")
    ap.add_argument("--preset", choices=["ds_cnn", "micro_speech"], default="ds_cnn",
                    help="오디오 프론트엔드 프리셋 (모델 학습 시점과 일치)")
    ap.add_argument("--device", type=int, default=None,
                    help="sounddevice 입력 장치 인덱스 (None=default)")
    ap.add_argument("--threads", type=int, default=1)
    ap.add_argument("--conf", type=float, default=0.60,
                    help="confidence threshold (기본 0.60)")
    ap.add_argument("--hop-ms", type=float, default=200.0)
    ap.add_argument("--print-every", type=int, default=5,
                    help="N invoke 마다 상태 출력 (기본 5)")
    ap.add_argument("--max-seconds", type=float, default=0,
                    help="최대 실행 시간 (0 = 무제한)")
    ap.add_argument("--list-devices", action="store_true", help="장치 목록만 출력")
    ap.add_argument("--json-summary", default=None, help="종료 시 SUMMARY JSON 저장")
    ap.add_argument("--countdown", type=int, default=3,
                    help="시작 전 카운트다운 초 (기본 3, 0=생략)")
    args = ap.parse_args()

    if args.list_devices:
        _list_devices()
        return

    if not args.model or not args.labels:
        ap.error("model 과 labels 는 필수입니다 (--list-devices 만 예외).")

    bus = ModeBus(initial=Mode.IDLE)
    worker = KWSWorker(
        model_path=args.model,
        labels_path=args.labels,
        preset_name=args.preset,
        bus=bus,
        input_device=args.device,
        threads=args.threads,
        confidence_threshold=args.conf,
        hop_ms=args.hop_ms,
    )

    print(f"== KWS mic infer ==")
    print(f"  model:   {args.model}")
    print(f"  labels:  {args.labels} ({len(worker.labels)} classes)")
    print(f"  preset:  {args.preset}")
    print(f"  device:  {args.device if args.device is not None else 'default'}")
    print(f"  conf_th: {args.conf}")
    print(f"  hop:     {args.hop_ms} ms")
    print()

    worker.start()

    # 3초 카운트다운 (사용자가 말할 준비 시간)
    if args.countdown > 0:
        print(f"\n마이크 준비 — {args.countdown}초 후 시작합니다...")
        for i in range(args.countdown, 0, -1):
            print(f"  {i}...", flush=True)
            time.sleep(1)
        print("\n→ 지금 발화하세요! (예: 'up', 'down', 'stop', 'go')\n")

    print("[start] listening (Ctrl+C to stop)")

    t_start = time.perf_counter()
    last_print = 0
    try:
        while True:
            time.sleep(0.2)
            elapsed = time.perf_counter() - t_start
            if args.max_seconds > 0 and elapsed >= args.max_seconds:
                break

            snap = worker.snapshot()
            invos = snap["stats"]["invocations"]
            if invos - last_print >= args.print_every:
                last_print = invos
                st = snap["stats"]
                mode_snap = bus.snapshot()
                lbl = st.get("last_label")
                conf = st.get("last_confidence")
                ms = st.get("last_invoke_ms")
                lbl_str = lbl if lbl else "-"
                conf_str = f"{conf:.2f}" if conf is not None else "-"
                ms_str = f"{ms:.1f}" if ms is not None else "-"
                print(f"[{invos:5d}] last={lbl_str:>10s} conf={conf_str}  "
                      f"invoke={ms_str}ms  "
                      f"det={st['detections']}  sil={st['silence_count']}  "
                      f"unk={st['unknown_count']}  sub={st['sub_threshold_count']}  "
                      f"mode={mode_snap['current_mode']}")

            # Bus 이벤트 소비 (외부 poll 없으면 계속 쌓임)
            ev = bus.poll()
            if ev:
                print(f"  ★ EVENT  src={ev.source} label={ev.label} "
                      f"→ mode={bus.get_mode().value}  conf={ev.confidence}")

    except KeyboardInterrupt:
        print("\n[stop] interrupted")
    finally:
        worker.stop()
        elapsed = time.perf_counter() - t_start
        snap = worker.snapshot()
        mode_snap = bus.snapshot()

        summary = {
            "elapsed_s": round(elapsed, 2),
            "invocations": snap["stats"]["invocations"],
            "detections": snap["stats"]["detections"],
            "silence_count": snap["stats"]["silence_count"],
            "unknown_count": snap["stats"]["unknown_count"],
            "sub_threshold_count": snap["stats"]["sub_threshold_count"],
            "avg_invoke_ms": (
                round(snap["stats"]["last_invoke_ms"], 2)
                if snap["stats"]["last_invoke_ms"] is not None else None
            ),
            "mode_bus": mode_snap,
            "worker_snapshot": snap,
        }

        print()
        print("=" * 64)
        print(f" SUMMARY  elapsed={elapsed:.1f}s  invocations={summary['invocations']}")
        print(f"   detections     : {summary['detections']}")
        print(f"   silence        : {summary['silence_count']}")
        print(f"   unknown        : {summary['unknown_count']}")
        print(f"   sub_threshold  : {summary['sub_threshold_count']}")
        print(f"   mode_switches  : {mode_snap['stats']['mode_switches']}")
        print(f"   final_mode     : {mode_snap['current_mode']}")
        print("=" * 64)

        if args.json_summary:
            Path(args.json_summary).parent.mkdir(parents=True, exist_ok=True)
            Path(args.json_summary).write_text(
                json.dumps(summary, indent=2), encoding="utf-8"
            )
            print(f"\n[json] {args.json_summary}")


if __name__ == "__main__":
    main()
