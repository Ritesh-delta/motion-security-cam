import cv2
import time
import os
import datetime
import logging
import requests
from dataclasses import dataclass
from pathlib import Path


@dataclass
class CameraConfig:
    source: int | str = 0
    frame_width: int = 640
    frame_height: int = 480
    fps_limit: int = 15


@dataclass
class MotionConfig:
    min_area: int = 800
    blur_kernel: tuple = (21, 21)
    threshold: int = 25
    dilate_iterations: int = 2
    cooldown_seconds: int = 5


@dataclass
class ThreatConfig:
    enabled: bool = False
    model_path: str = ""
    class_names_path: str = ""
    confidence_threshold: float = 0.5
    input_size: tuple = (640, 640)
    watch_classes: tuple = ("knife", "gun", "pistol", "rifle", "fire")
    red_alert_cooldown_seconds: int = 15


@dataclass
class NtfyConfig:
    topic: str = os.environ.get("NTFY_TOPIC", "my-security-cam-CHANGE-ME-123")
    server: str = os.environ.get("NTFY_SERVER", "https://ntfy.sh")


@dataclass
class RecordingConfig:
    output_dir: str = "recordings"
    pre_event_seconds: int = 2
    post_event_seconds: int = 5
    codec: str = "mp4v"


class CameraStream:
    def __init__(self, config: CameraConfig):
        self.config = config
        self.cap = None

    def start(self):
        self.cap = cv2.VideoCapture(self.config.source)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.frame_width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.frame_height)
        if not self.cap.isOpened():
            raise RuntimeError(f"Could not open camera source: {self.config.source}")
        logging.info("Camera stream started.")

    def read(self):
        ok, frame = self.cap.read()
        if not ok:
            return None
        return frame

    def stop(self):
        if self.cap:
            self.cap.release()
        logging.info("Camera stream stopped.")


class MotionDetector:
    def __init__(self, config: MotionConfig):
        self.config = config
        self.reference_frame = None
        self.last_event_time = 0.0

    def _preprocess(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, self.config.blur_kernel, 0)
        return gray

    def detect(self, frame) -> tuple[bool, list]:
        gray = self._preprocess(frame)

        if self.reference_frame is None:
            self.reference_frame = gray
            return False, []

        frame_delta = cv2.absdiff(self.reference_frame, gray)
        thresh = cv2.threshold(frame_delta, self.config.threshold, 255, cv2.THRESH_BINARY)[1]
        thresh = cv2.dilate(thresh, None, iterations=self.config.dilate_iterations)

        contours, _ = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        boxes = []
        for c in contours:
            if cv2.contourArea(c) < self.config.min_area:
                continue
            boxes.append(cv2.boundingRect(c))

        self.reference_frame = cv2.addWeighted(self.reference_frame, 0.95, gray, 0.05, 0)

        motion_detected = len(boxes) > 0
        return motion_detected, boxes

    def is_in_cooldown(self) -> bool:
        return (time.time() - self.last_event_time) < self.config.cooldown_seconds

    def mark_event(self):
        self.last_event_time = time.time()


class ThreatDetector:
    def __init__(self, config: ThreatConfig):
        self.config = config
        self.net = None
        self.class_names = []
        self.last_alert_time = 0.0

        if self.config.enabled and self.config.model_path:
            self._load_model()

    def _load_model(self):
        try:
            self.net = cv2.dnn.readNet(self.config.model_path)
            if self.config.class_names_path and os.path.exists(self.config.class_names_path):
                with open(self.config.class_names_path) as f:
                    self.class_names = [line.strip() for line in f if line.strip()]
            logging.info(f"Threat-detection model loaded: {self.config.model_path}")
        except Exception as e:
            logging.error(f"Could not load threat-detection model: {e}")
            self.net = None

    def is_in_cooldown(self) -> bool:
        return (time.time() - self.last_alert_time) < self.config.red_alert_cooldown_seconds

    def mark_alert(self):
        self.last_alert_time = time.time()

    def detect(self, frame) -> list:
        if not self.config.enabled or self.net is None:
            return []

        h, w = frame.shape[:2]
        blob = cv2.dnn.blobFromImage(frame, 1 / 255.0, self.config.input_size, swapRB=True, crop=False)
        self.net.setInput(blob)
        outputs = self.net.forward()

        threats = []
        try:
            predictions = outputs[0]
            for pred in predictions:
                scores = pred[5:]
                class_id = int(scores.argmax())
                confidence = float(scores[class_id]) * float(pred[4])
                if confidence < self.config.confidence_threshold:
                    continue

                class_name = self.class_names[class_id] if class_id < len(self.class_names) else str(class_id)
                if class_name.lower() not in self.config.watch_classes:
                    continue

                cx, cy, bw, bh = pred[0:4]
                x = int((cx - bw / 2) * w)
                y = int((cy - bh / 2) * h)
                box = (x, y, int(bw * w), int(bh * h))
                threats.append((class_name, confidence, box))
        except Exception as e:
            logging.error(f"Error parsing threat-detection output: {e}")

        return threats


class EventRecorder:
    def __init__(self, config: RecordingConfig, camera_config: CameraConfig):
        self.config = config
        self.camera_config = camera_config
        self.writer = None
        self.recording = False
        self.stop_at = 0.0
        Path(self.config.output_dir).mkdir(parents=True, exist_ok=True)

    def start_clip(self):
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = os.path.join(self.config.output_dir, f"motion_{timestamp}.mp4")
        fourcc = cv2.VideoWriter_fourcc(*self.config.codec)
        self.writer = cv2.VideoWriter(
            filepath, fourcc, self.camera_config.fps_limit,
            (self.camera_config.frame_width, self.camera_config.frame_height)
        )
        self.recording = True
        logging.info(f"Recording started: {filepath}")

    def write_frame(self, frame):
        if self.recording and self.writer is not None:
            self.writer.write(frame)

    def extend_recording(self):
        self.stop_at = time.time() + self.config.post_event_seconds

    def maybe_stop(self):
        if self.recording and time.time() >= self.stop_at:
            self.stop_clip()

    def stop_clip(self):
        if self.writer is not None:
            self.writer.release()
        self.writer = None
        self.recording = False
        logging.info("Recording stopped.")


class NtfyNotifier:
    def __init__(self, config: NtfyConfig, cooldown_seconds: int = 30):
        self.config = config
        self.cooldown_seconds = cooldown_seconds
        self.last_alert_time = 0.0

    def notify(self, message: str, image_path: str | None = None, urgent: bool = False):
        if (time.time() - self.last_alert_time) < self.cooldown_seconds:
            return
        self.last_alert_time = time.time()

        logging.info(f"ALERT: {message}")

        url = f"{self.config.server.rstrip('/')}/{self.config.topic}"
        headers = {
            "Title": "Security Cam Alert",
            "Priority": "urgent" if urgent else "default",
            "Tags": "rotating_light" if urgent else "warning",
        }

        try:
            if image_path and os.path.exists(image_path):
                headers["Filename"] = os.path.basename(image_path)
                headers["Message"] = message
                with open(image_path, "rb") as f:
                    resp = requests.put(url, data=f, headers=headers, timeout=10)
            else:
                resp = requests.post(url, data=message.encode("utf-8"), headers=headers, timeout=10)

            if resp.status_code == 200:
                logging.info("Alert sent via ntfy.sh.")
            else:
                logging.error(f"ntfy.sh returned status {resp.status_code}: {resp.text}")
        except Exception as e:
            logging.error(f"Failed to send ntfy.sh alert: {e}")


class SnapshotSaver:
    def __init__(self, output_dir: str = "snapshots"):
        self.output_dir = output_dir
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)

    def save(self, frame) -> str:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"motion_{timestamp}.jpg"
        filepath = os.path.join(self.output_dir, filename)
        cv2.imwrite(filepath, frame)
        return filepath


class EventLogger:
    def __init__(self, output_path: str = "events.csv"):
        self.output_path = output_path
        if not os.path.exists(self.output_path):
            with open(self.output_path, "w") as f:
                f.write("timestamp,event_type,details,snapshot_path\n")

    def log(self, event_type: str, details: str, snapshot_path: str = ""):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        details = details.replace(",", ";")
        with open(self.output_path, "a") as f:
            f.write(f"{timestamp},{event_type},{details},{snapshot_path}\n")


class SecurityCamApp:
    def __init__(self):
        self.camera_config = CameraConfig()
        self.motion_config = MotionConfig()
        self.recording_config = RecordingConfig()
        self.ntfy_config = NtfyConfig()
        self.threat_config = ThreatConfig()

        self.camera = CameraStream(self.camera_config)
        self.detector = MotionDetector(self.motion_config)
        self.recorder = EventRecorder(self.recording_config, self.camera_config)
        self.notifier = NtfyNotifier(self.ntfy_config, cooldown_seconds=30)
        self.snapshot_saver = SnapshotSaver()
        self.threat_detector = ThreatDetector(self.threat_config)
        self.event_logger = EventLogger()

    def run(self, show_preview: bool = True):
        logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
        self.camera.start()

        if show_preview:
            cv2.namedWindow("Security Cam", cv2.WINDOW_NORMAL)
            cv2.setWindowProperty("Security Cam", cv2.WND_PROP_TOPMOST, 1)

        try:
            while True:
                frame = self.camera.read()
                if frame is None:
                    logging.warning("Failed to read frame; retrying...")
                    time.sleep(0.5)
                    continue

                motion, boxes = self.detector.detect(frame)

                threats = self.threat_detector.detect(frame)
                if threats and not self.threat_detector.is_in_cooldown():
                    self.threat_detector.mark_alert()
                    names = ", ".join(sorted({t[0] for t in threats}))
                    snapshot_path = self.snapshot_saver.save(frame)
                    self.notifier.notify(
                        f"RED ALERT: dangerous object detected ({names})!",
                        image_path=snapshot_path,
                        urgent=True,
                    )
                    self.event_logger.log("threat", names, snapshot_path)
                    if not self.recorder.recording:
                        self.recorder.start_clip()
                    self.recorder.extend_recording()

                if motion and not self.detector.is_in_cooldown():
                    self.detector.mark_event()
                    snapshot_path = self.snapshot_saver.save(frame)
                    self.notifier.notify("Motion detected at your camera!", image_path=snapshot_path)
                    self.event_logger.log("motion", f"{len(boxes)} region(s)", snapshot_path)
                    if not self.recorder.recording:
                        self.recorder.start_clip()
                    self.recorder.extend_recording()

                if self.recorder.recording:
                    self.recorder.write_frame(frame)
                    self.recorder.maybe_stop()

                if show_preview:
                    for (x, y, w, h) in boxes:
                        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                    for (name, conf, (x, y, w, h)) in threats:
                        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 0, 255), 3)
                        cv2.putText(frame, f"{name} {conf:.0%}", (x, max(y - 8, 0)),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                    if threats:
                        h_frame, w_frame = frame.shape[:2]
                        cv2.rectangle(frame, (0, 0), (w_frame - 1, h_frame - 1), (0, 0, 255), 8)
                    cv2.imshow("Security Cam", frame)
                    key = cv2.waitKey(1) & 0xFF
                    if key == ord('q') or key == 27:
                        logging.info("Stop key pressed, stopping...")
                        break

        except KeyboardInterrupt:
            logging.info("Ctrl+C received, stopping...")
        finally:
            self.recorder.stop_clip()
            self.camera.stop()
            cv2.destroyAllWindows()
            logging.info("Security cam stopped cleanly.")


if __name__ == "__main__":
    app = SecurityCamApp()
    app.run(show_preview=True)