# M-Touch

A real-time multi-touch input system that converts Hokuyo LiDAR scanner data into TUIO 1.1 touch events. Detects hand/object touches on a surface using LiDAR scanning and outputs normalized touch coordinates to any TUIO-compatible application.

## Features

- **Multi-Sensor** — Configure multiple Hokuyo LiDAR sensors with independent processing pipelines
- **Multi-Screen** — Map touches to multiple logical screens with independent coordinate systems
- **Multi-Output** — Route touches to multiple TUIO servers simultaneously
- **Real-Time Pipeline** — Background learning/subtraction, DBSCAN clustering, persistent touch tracking
- **Interactive GUI** — Live scan visualization, pan/zoom canvas, drag-to-move sensor/screen positioning
- **Mock Mode** — Simulated scanner for testing without hardware

## Supported Hardware

| Sensor | Range | Field of View |
|--------|-------|---------------|
| Hokuyo UST-10LX | 10m | 270° |
| Hokuyo UST-20LX | 20m | 270° |

## Installation

```bash
pip install -r requirements.txt
```

### Dependencies

- `hokuyolx` — Hokuyo LiDAR driver
- `python-osc` — TUIO/OSC messaging
- `numpy` — Scan data processing
- `scikit-learn` — DBSCAN clustering
- `PyQt5` — GUI

## Usage

```bash
# Mock mode (no hardware)
python main.py --mock

# Real hardware
python main.py

# Custom settings file
python main.py --settings config.json
```

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `R` | Reset/center canvas view |
| `M` (hold) | Move mode — drag sensors and screens on canvas |
| `Ctrl+S` | Save settings |
| `Ctrl+O` | Load settings |
| `Ctrl+Q` | Exit |

## TUIO Output

Sends TUIO 1.1 `/tuio/2Dcur` messages over UDP. Default target: `127.0.0.1:3333`.

## License

MIT
