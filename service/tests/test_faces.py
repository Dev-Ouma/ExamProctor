from pathlib import Path

import cv2
import numpy as np
import pytest

from examproctor_service.analysis.faces import FaceEngine, cosine

MODELS = Path(__file__).resolve().parents[1] / "models"
needs_models = pytest.mark.skipif(
    not (MODELS / "face_detection_yunet_2023mar.onnx").exists(),
    reason="run `make models` to download the face models",
)


def jpeg(image) -> bytes:
    return cv2.imencode(".jpg", image)[1].tobytes()


@needs_models
def test_black_frame_is_blank_with_no_faces():
    result = FaceEngine(MODELS).analyse(jpeg(np.zeros((480, 640, 3), np.uint8)))

    assert result.faces == []
    assert result.blank is True
    assert result.embedding is None


@needs_models
def test_textured_frame_without_a_face():
    rng = np.random.default_rng(1)
    result = FaceEngine(MODELS).analyse(jpeg(rng.integers(0, 255, (480, 640, 3), dtype=np.uint8)))

    assert result.faces == []
    assert result.blank is False


@needs_models
def test_garbage_bytes_are_a_decode_error_not_a_crash():
    result = FaceEngine(MODELS).analyse(b"not a jpeg")
    assert result.decode_error and not result.blank


def test_model_hash_is_checked(tmp_path):
    (tmp_path / "face_detection_yunet_2023mar.onnx").write_bytes(b"tampered")
    with pytest.raises(RuntimeError, match="sha256"):
        FaceEngine(tmp_path)


def test_cosine():
    assert cosine([1, 0], [1, 0]) == pytest.approx(1.0)
    assert cosine([1, 0], [0, 1]) == pytest.approx(0.0)
