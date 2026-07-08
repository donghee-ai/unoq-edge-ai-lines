#!/usr/bin/env python3
"""KWS 모델 다운로드 helper — 다중 URL fallback + SHA256 검증.

정책:
  - Apache-2.0 / CC BY 4.0 라이선스 모델만 시도
  - 실패 시 각 후보 URL 을 순서대로 시도
  - 마지막 fallback 은 git clone 안내 메시지 출력

사용:
  python3 scripts/download_model.py --model ds_cnn --dest models/
  python3 scripts/download_model.py --model micro_speech --dest models/
  python3 scripts/download_model.py --list

주의:
  URL 은 시간이 지나면 변경될 수 있음. 실패 시 수동 clone 안내 참조.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sys
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen


# 모델 카탈로그
# expected_sha256 은 알려진 값이 있으면 채워둠 (없으면 None → 크기만 검증)
CATALOG = {
    "ds_cnn": {
        "filename": "kws_ref_model_ds_cnn_int8.tflite",
        "license": "Apache-2.0 (code) + CC BY 4.0 (data)",
        "vocab": 12,
        "expected_size_min": 40 * 1024,     # 40 KB 이상
        "expected_size_max": 200 * 1024,    # 200 KB 이하 (MLPerf Tiny 참조 ~52KB)
        # 2026-07-02 UNO Q 첫 다운로드 성공 시 확인 (53936 bytes)
        "expected_sha256": "aeea436800704fce17b17292e4412630ad856e9d777c044c64ef748a880bd0ae",
        "urls": [
            # MLPerf Tiny reference model (여러 미러 시도 순서)
            "https://github.com/mlcommons/tiny/raw/master/benchmark/training/keyword_spotting/trained_models/kws_ref_model.tflite",
            "https://raw.githubusercontent.com/mlcommons/tiny/master/benchmark/training/keyword_spotting/trained_models/kws_ref_model.tflite",
        ],
        "labels": [
            "Down", "Go", "Left", "No", "Off", "On",
            "Right", "Stop", "Up", "Yes", "_silence_", "_unknown_",
        ],
        "manual_fallback": (
            "git clone --depth 1 https://github.com/mlcommons/tiny /tmp/mlperf-tiny\n"
            "cp /tmp/mlperf-tiny/benchmark/training/keyword_spotting/trained_models/kws_ref_model.tflite models/kws_ref_model_ds_cnn_int8.tflite"
        ),
    },
    "micro_speech": {
        "filename": "micro_speech.tflite",
        "license": "Apache-2.0",
        "vocab": 4,
        "expected_size_min": 10 * 1024,
        "expected_size_max": 30 * 1024,
        "expected_sha256": None,
        "urls": [
            # tflite-micro repo 의 micro_speech quantized model (다양한 미러)
            "https://github.com/tensorflow/tflite-micro/raw/main/tensorflow/lite/micro/examples/micro_speech/models/micro_speech_quantized.tflite",
            "https://raw.githubusercontent.com/tensorflow/tflite-micro/main/tensorflow/lite/micro/examples/micro_speech/models/micro_speech_quantized.tflite",
        ],
        "labels": ["_silence_", "_unknown_", "yes", "no"],
        "manual_fallback": (
            "git clone --depth 1 https://github.com/tensorflow/tflite-micro /tmp/tflm\n"
            "cp /tmp/tflm/tensorflow/lite/micro/examples/micro_speech/models/*.tflite models/"
        ),
    },
}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _download(url: str, dest: Path, timeout: int = 30) -> bool:
    print(f"  try: {url}")
    try:
        req = Request(url, headers={"User-Agent": "unoq-kws/1.0"})
        with urlopen(req, timeout=timeout) as resp:
            data = resp.read()
        dest.write_bytes(data)
        return True
    except (URLError, TimeoutError, OSError) as e:
        print(f"    fail: {e}")
        if dest.exists() and dest.stat().st_size == 0:
            dest.unlink()
        return False


def download_model(model_key: str, dest_dir: Path, force: bool = False) -> Path:
    if model_key not in CATALOG:
        raise ValueError(f"unknown model: {model_key}. try --list")
    meta = CATALOG[model_key]
    dest = dest_dir / meta["filename"]

    print(f"\n=== Download KWS model: {model_key} ===")
    print(f"  license: {meta['license']}")
    print(f"  vocab:   {meta['vocab']} classes")
    print(f"  dest:    {dest}")

    if dest.exists() and not force:
        size = dest.stat().st_size
        print(f"  already exists: {size} bytes")
        _verify(dest, meta)
        return dest

    dest_dir.mkdir(parents=True, exist_ok=True)
    ok = False
    for url in meta["urls"]:
        if _download(url, dest):
            ok = True
            break

    if not ok:
        print("\n[FAIL] 모든 URL 실패. 수동 다운로드:\n")
        print(meta["manual_fallback"])
        sys.exit(2)

    _verify(dest, meta)

    # labels 파일도 생성 (없으면)
    labels_path = dest_dir.parent / "scripts" / f"labels_{meta['vocab']}.txt"
    if not labels_path.exists():
        try:
            labels_path.parent.mkdir(parents=True, exist_ok=True)
            labels_path.write_text("\n".join(meta["labels"]) + "\n", encoding="utf-8")
            print(f"  labels: {labels_path}")
        except Exception as e:
            print(f"  (labels write skipped: {e})")

    return dest


def _verify(dest: Path, meta: dict):
    size = dest.stat().st_size
    print(f"\n  verify: size={size} bytes")
    if size < meta["expected_size_min"] or size > meta["expected_size_max"]:
        print(
            f"    [WARN] size out of expected range "
            f"({meta['expected_size_min']}~{meta['expected_size_max']})"
        )
        print("    다운로드된 파일이 정상 모델이 아닐 수 있습니다.")
        print("    수동 검증 권장:")
        print(f"      python3 scripts/inspect_kws.py {dest}")

    hashv = _sha256(dest)
    if meta.get("expected_sha256"):
        if hashv == meta["expected_sha256"]:
            print(f"    sha256: OK ({hashv[:16]}...)")
        else:
            print(f"    [WARN] sha256 mismatch")
            print(f"      expected: {meta['expected_sha256']}")
            print(f"      got:      {hashv}")
    else:
        print(f"    sha256: {hashv}")
        print("    (참조용 — expected_sha256 미핀. 처음 성공 시 CATALOG 에 기록 권장)")


def _list():
    print("\n지원 모델:")
    for k, meta in CATALOG.items():
        print(f"\n  {k}")
        print(f"    file:    {meta['filename']}")
        print(f"    license: {meta['license']}")
        print(f"    vocab:   {meta['vocab']} classes")
        print(f"    urls:    {len(meta['urls'])} 후보")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="ds_cnn",
                    help="ds_cnn | micro_speech (default: ds_cnn)")
    ap.add_argument("--dest", default="models",
                    help="다운로드 저장 경로 (default: models/)")
    ap.add_argument("--force", action="store_true",
                    help="이미 파일이 있어도 재다운로드")
    ap.add_argument("--list", action="store_true",
                    help="지원 모델 목록 출력 후 종료")
    args = ap.parse_args()

    if args.list:
        _list()
        return

    dest = download_model(args.model, Path(args.dest), force=args.force)
    print(f"\n[done] {dest}\n")
    print("다음 단계:")
    print(f"  python3 scripts/inspect_kws.py {dest}")
    print(f"  python3 scripts/benchmark_kws.py --model {dest} --json benchmarks/kws_bench.json")


if __name__ == "__main__":
    main()
