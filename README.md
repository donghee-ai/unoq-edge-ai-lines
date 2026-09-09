# UNO Q Edge AI Lines

> 한국어: [`README_kr.md`](README_kr.md)

> **How much object detection, pose estimation, and speech recognition can you run on
> an Arduino UNO Q (Qualcomm Dragonwing QRB2210, Cortex-A53 ×4) with no NPU — CPU only?
> This repo is the measurement record.**

This is a measurement repo, not a product. Its entire purpose was to confirm on real
hardware what "no NPU, this is what you get" actually means, and to leave the evidence
behind. The product line built from the Pose assets validated here lives in a separate
repo: [`health_care_bot`](https://github.com/donghee-ai/health_care_bot).

Measurement finished in the 2026-06 cycle, and this repo is closed as that record.

## Results

**Every number below was measured by us on real UNO Q hardware.** No vendor-published
figures are mixed in.

| Line | Model | Size | e2e | Verdict |
|---|---|---|---|---|
| Vision | YOLOv8n int8 TFLite | 3.19 MB | **9.23 FPS** | pass |
| Pose | MoveNet Thunder INT8 TFLite | 6.80 MB | **9.69 FPS** | pass |
| ASR | Whisper Tiny.en TFLite (DRQ) | 39.7 MB | **3.18 s** (11 s audio) | pass |

Pass criteria: e2e FPS ≥ 8 · RSS ≪ 2.4 GB · thermal ≤ 70 °C · dropped frames = 0

All three lines are **bound by `invoke` (inference)**. Preprocessing, postprocessing and
drawing together account for only 13–22 %. That is why turning the display off barely
moves the FPS.

> **The fourth line (KWS) was never measured.** The cycle ended after candidate selection
> and license review, so the implementation was removed from the repo along with it. The
> research survived — [`docs/lessons.md`](docs/lessons.md) §1-5, which is the single most
> reusable table in this repo.

> **Thermal has no headroom.** A short run read 68.6 °C, but sustained operation climbed
> to 71.4 °C and crossed the limit. No soak test was performed.

## Documentation

Two pages are enough.

| Document | Contents |
|---|---|
| [`docs/measurements.md`](docs/measurements.md) | **All measurements** — environment, conditions, numbers, per-stage breakdown, what was not measured |
| [`docs/lessons.md`](docs/lessons.md) | **Judgments worth reusing** — model selection filters, licensing, six traps we walked into |

> Both documents are written in Korean. This README is the English entry point; the
> tables, numbers and command lines in them are readable without Korean, and the section
> numbers referenced here match.

The three findings most worth carrying to another project:

- **Qualcomm AI Hub models do not run on QRB2210.** The `.onnx` we downloaded was actually
  a QNN context binary compiled for a different chip — the `EPContext` node is the proof.
- **Do not trust the model card; open the tensors.** A Whisper build labeled "int8" turned
  out to be weight-only DRQ, with int8 tensors making up just 6.8 % of the model.
- **"Only a Billboard Device shows up" means suspect the cable first**, not the hub,
  the port, or the driver.

## Layout

```text
unoq-edge-ai-lines/
├── docs/                  the two documents above (Korean)
├── vision/                YOLOv8n int8 — code · Dockerfile · benchmarks/*.json
├── pose/                  MoveNet Thunder — code · Dockerfile
│   └── ptz/               PTZ PoC (fork of Shawn Hymel's project, MIT).
│                          Follow-up work moved to health_care_bot
└── asr/                   Whisper Tiny.en — code · Dockerfile
```

**Model sources and licenses are in [`docs/lessons.md`](docs/lessons.md) §1-2**, including
download URLs. Everything is third-party. **YOLOv8n weights are not kept in this repo
because they are AGPL-3.0** (§1-4). You do not need to obtain them separately — one export
command inside the container below produces them, since `ultralytics` is already in the
image and `yolov8n.pt` is fetched automatically.

Of the raw measurement artifacts, only `vision/benchmarks/*.json` are machine-readable.

## Running it

```bash
cd vision && bash docker/run-vision.sh              # enter the container (vision/ is mounted at /work)

# inside the container — once, to produce the model
yolo export model=yolov8n.pt format=tflite int8=True imgsz=320
```

`imgsz=320` is required: `postprocess.py` is written for 320 input (2100 anchors), and the
9.23 FPS above was measured at that size.

**The model is not baked into the image.** The Dockerfile installs Python packages only,
and `vision/` is bind-mounted, so the export output lands on the host. `*.tflite` is
gitignored, so it will not be committed by accident.

On the device everything runs under `~/venv-unoq` with `ai-edge-litert`. Setup steps are in
[`docs/measurements.md`](docs/measurements.md) §1.

## How to read the numbers here

- Figures in the tables are **ours**. Anything quoted from a vendor, paper or leaderboard
  is marked with its source.
- **What was not measured says "not measured."** No results table is padded with blanks or
  `?` — that looks like data exists when it does not, which is worse than saying nothing.
- KWS measurement and a soak thermal test were never done, and leaving that stated plainly
  is how this record closes.

---

**Author**: DongHee Kim (Hansung University) · **Repo**: `donghee-ai/unoq-edge-ai-lines`
