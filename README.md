# 🚨 Motion-Triggered Security Cam

A Python/OpenCV security camera that monitors a webcam, detects motion, saves snapshots, records video clips, logs events to CSV, and optionally sends push notifications through **ntfy**.

## ✨ Features

- 🎥 Webcam monitoring with OpenCV
- 🟢 Frame-difference motion detection
- 📸 Snapshot on motion
- 🎬 Automatic MP4 recording with post-motion buffer
- 📱 Optional ntfy push notifications
- 🚨 Optional ONNX/OpenCV DNN threat detection
- 🧾 CSV event logging
- 🛑 Clean shutdown with `q`, `ESC`, or `Ctrl+C`
- 🔒 Private runtime files excluded from Git

## 📁 Project Structure

```text
motion-security-cam/
├── detection.py
├── requirements.txt
├── .env.example
├── .gitignore
├── LICENSE
├── README.md
├── recordings/
│   └── .gitkeep
└── snapshots/
    └── .gitkeep
```

Runtime files:
```text
events.csv
recordings/*.mp4
snapshots/*.jpg
```

These are intentionally ignored by Git.

## 🧠 How It Works

```text
Webcam
   │
   ▼
OpenCV Frame Capture
   │
   ├──► Motion Detector ──► Snapshot ──► CSV Log
   │                       ├───────────► ntfy Alert
   │                       └───────────► Video Recording
   │
   └──► Optional ONNX Threat Detector ──► Red Alert
```

Motion detection converts frames to grayscale, blurs them, compares the current frame with a continuously updated reference frame, thresholds the difference, dilates the result, and finds significant contours.

## 🛠️ Requirements

- Python 3.10+
- Webcam
- Windows, macOS, or Linux
- Internet only for ntfy notifications

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

## 🚀 Run

```bash
python detection.py
```

### Windows PowerShell

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python detection.py
```

### macOS/Linux

```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
python detection.py
```

## 📱 ntfy Notifications

The application works without notifications. To enable them, create a private/unpredictable topic and set:

### PowerShell

```powershell
$env:NTFY_TOPIC="your-private-topic-name"
python detection.py
```

### macOS/Linux

```bash
export NTFY_TOPIC="your-private-topic-name"
python detection.py
```

Optional server:

```text
NTFY_SERVER=https://ntfy.sh
```

Do **not** commit your real topic or `.env` file.

## ⚙️ Configuration

The main configuration is in `detection.py`.

### Camera

```python
CameraConfig(
    source=0,
    frame_width=640,
    frame_height=480,
    fps_limit=15,
)
```

Use `source=1` for another camera if required.

### Motion

```python
MotionConfig(
    min_area=800,
    blur_kernel=(21, 21),
    threshold=25,
    dilate_iterations=2,
    cooldown_seconds=5,
)
```

Too many false detections? Increase `min_area`.

Missing movement? Try decreasing `min_area` or `threshold`.

### Recording

```python
RecordingConfig(
    output_dir="recordings",
    post_event_seconds=5,
    codec="mp4v",
)
```

Recordings are saved as:

```text
recordings/motion_YYYYMMDD_HHMMSS.mp4
```

### Snapshots

Snapshots are saved as:

```text
snapshots/motion_YYYYMMDD_HHMMSS_microseconds.jpg
```

## 🚨 Optional Threat Detection

Threat detection is disabled by default.

It can be enabled with an ONNX model:

```python
ThreatConfig(
    enabled=True,
    model_path="models/model.onnx",
    class_names_path="models/classes.txt",
)
```

The model is **not included**. The current parser expects YOLO-style output:

```text
[cx, cy, width, height, objectness, class_scores...]
```

Different models may require a different output parser.

Default watched classes include:

```text
knife, gun, pistol, rifle, fire
```

## 🧾 Event Log

Events are stored in:

```text
events.csv
```

Example:

```csv
timestamp,event_type,details,snapshot_path
2026-08-21 18:00:00,motion,2 region(s),snapshots/motion_....jpg
```

The file is ignored by Git because it can contain private timestamps and local paths.

## 🛑 Stop the Camera

Click the OpenCV window and press:

```text
q
```

or:

```text
ESC
```

You can also press:

```text
Ctrl+C
```

in the terminal.

## 🐛 Troubleshooting

### Camera does not open

Try:

```python
source=1
```

and make sure another application is not using the webcam.

### `No module named cv2`

```bash
python -m pip install -r requirements.txt
```

### ntfy notifications do not arrive

Check:

```powershell
echo $env:NTFY_TOPIC
```

and confirm your phone is subscribed to the exact same topic.

### Too many motion alerts

Increase:

```python
min_area
cooldown_seconds
```

### Motion is not detected

Decrease:

```python
min_area
threshold
```

## 🔐 Security & Privacy

Do not upload:

```text
.env
events.csv
recordings/
snapshots/
```

These are already covered by `.gitignore`.

Use a long, unpredictable ntfy topic. Treat the topic as a secret because anyone who knows it may be able to publish messages to it.

The application processes camera frames locally by default. Only notification requests are sent externally when ntfy is configured.

## 📌 Limitations

This is a personal/learning project, not a professional security system.

- Frame-difference detection can produce false positives.
- Lighting changes may trigger motion.
- The camera must remain connected.
- Threat detection depends on the supplied model.
- Video codec support can vary by OS.
- There is no cloud backup or remote video streaming.

## 🔮 Future Improvements

- [ ] Pre-motion video buffer
- [ ] Camera reconnect logic
- [ ] Configurable recording duration
- [ ] Web dashboard
- [ ] SQLite event database
- [ ] Multiple cameras
- [ ] Person detection
- [ ] Better object detection
- [ ] Telegram/email alerts
- [ ] Docker support
- [ ] Automated tests
- [ ] Background/service mode

## 👨‍💻 Learning Goals

This project demonstrates:

- Python
- OOP and dataclasses
- OpenCV
- Computer vision
- Motion detection
- Video recording
- HTTP APIs
- Environment variables
- Logging
- CSV handling
- ONNX/OpenCV DNN
- Git/GitHub project organization

## 📜 License

MIT License. See `LICENSE`.

## ⚠️ Disclaimer

Use this project responsibly and only where you have appropriate authorization to monitor or record. Follow applicable privacy and surveillance laws.
