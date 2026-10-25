"""Face detection (YuNet, MIT) and face matching (SFace, Apache-2.0) on OpenCV, CPU only.

Both models are the licence-clean options DeepFace also offers; calling OpenCV directly avoids
pulling TensorFlow into the worker.
"""

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

YUNET = (
    "face_detection_yunet_2023mar.onnx",
    "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4",
)
SFACE = (
    "face_recognition_sface_2021dec.onnx",
    "0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79",
)

# OpenCV's published SFace cosine threshold (same person when similarity >= 0.363).
SFACE_COSINE_THRESHOLD = 0.363
# Faces narrower than this are not embedded: upscaled crops give unreliable matches.
MIN_FACE_PIXELS = 112
# Frames are scaled so the longer side is at most this before detection.
MAX_SIDE = 640


@dataclass
class Face:
    box: tuple[int, int, int, int]  # x, y, w, h in the analysed image
    score: float
    yaw: float  # nose offset from the eye midpoint, in eye distances; |yaw| > 0.35 = turned away


@dataclass
class FrameResult:
    faces: list[Face] = field(default_factory=list)
    brightness: float = 0.0  # mean grey level 0-255
    contrast: float = 0.0  # grey standard deviation
    sharpness: float = 0.0  # variance of the Laplacian
    embedding: list[float] | None = None  # largest face, only if wide enough
    largest_face_px: int = 0
    decode_error: bool = False

    @property
    def blank(self) -> bool:
        """Covered lens, black screen share or a uniform frame."""
        return not self.decode_error and (self.contrast < 8 or self.brightness < 20)

    def to_json(self) -> dict:
        return {
            "faces": [{"box": f.box, "score": round(f.score, 3), "yaw": round(f.yaw, 3)} for f in self.faces],
            "brightness": round(self.brightness, 1),
            "contrast": round(self.contrast, 1),
            "sharpness": round(self.sharpness, 1),
            "largest_face_px": self.largest_face_px,
            "blank": self.blank,
            "decode_error": self.decode_error,
        }


def verify_model(path: Path, sha256: str) -> Path:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != sha256:
        raise RuntimeError(f"model {path.name} has sha256 {digest}, expected {sha256}")
    return path


class FaceEngine:
    def __init__(self, model_dir: Path) -> None:
        self.detector = cv2.FaceDetectorYN.create(
            str(verify_model(model_dir / YUNET[0], YUNET[1])), "", (320, 320), 0.8, 0.3, 20
        )
        self.recognizer = cv2.FaceRecognizerSF.create(str(verify_model(model_dir / SFACE[0], SFACE[1])), "")

    def analyse(self, jpeg: bytes, embed: bool = True) -> FrameResult:
        image = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            return FrameResult(decode_error=True)
        scale = min(1.0, MAX_SIDE / max(image.shape[:2]))
        if scale < 1.0:
            image = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        grey = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        result = FrameResult(
            brightness=float(grey.mean()),
            contrast=float(grey.std()),
            sharpness=float(cv2.Laplacian(grey, cv2.CV_64F).var()),
        )
        h, w = image.shape[:2]
        self.detector.setInputSize((w, h))
        _, detections = self.detector.detect(image)
        if detections is None:
            return result
        for d in detections:
            x, y, fw, fh = (int(v) for v in d[:4])
            right_eye, left_eye, nose = d[4:6], d[6:8], d[8:10]
            eye_mid = (right_eye + left_eye) / 2
            eye_dist = float(np.linalg.norm(left_eye - right_eye)) or 1.0
            result.faces.append(Face((x, y, fw, fh), float(d[14]), float((nose[0] - eye_mid[0]) / eye_dist)))
        largest = max(detections, key=lambda d: d[2] * d[3])
        result.largest_face_px = int(min(largest[2], largest[3]))
        if embed and result.largest_face_px >= MIN_FACE_PIXELS:
            aligned = self.recognizer.alignCrop(image, largest)
            result.embedding = self.recognizer.feature(aligned).flatten().tolist()
        return result


def cosine(a: list[float], b: list[float]) -> float:
    va, vb = np.asarray(a, dtype=np.float32), np.asarray(b, dtype=np.float32)
    denom = float(np.linalg.norm(va) * np.linalg.norm(vb)) or 1.0
    return float(va @ vb / denom)
