import cv2
import numpy as np

from app.services.blending import feather_blend
from app.services.global_align import align_global
from app.services.mask import process_mask


def make_feature_image(width=640, height=480):
    image = np.zeros((height, width, 3), dtype=np.uint8)
    rng = np.random.default_rng(42)
    for _ in range(120):
        x, y = rng.integers(20, width - 20), rng.integers(20, height - 20)
        color = tuple(int(v) for v in rng.integers(80, 255, 3))
        cv2.circle(image, (int(x), int(y)), int(rng.integers(3, 10)), color, -1)
    cv2.putText(image, "BEST SHOT", (140, 240), cv2.FONT_HERSHEY_SIMPLEX, 1.6, (255, 255, 255), 3)
    return image


def test_global_alignment_recovers_translation():
    main = make_feature_image()
    transform = np.float32([[1, 0, 14], [0, 1, -9]])
    source = cv2.warpAffine(main, transform, (main.shape[1], main.shape[0]))
    result = align_global(main, source)
    assert result.inlier_count >= 10
    assert result.inlier_ratio >= 0.25
    assert result.reprojection_error < 3.0
    difference = np.mean(cv2.absdiff(main[30:-30, 30:-30], result.aligned[30:-30, 30:-30]))
    assert difference < 8.0


def test_mask_and_feather_blend():
    base = np.zeros((100, 120, 3), dtype=np.uint8)
    source = np.full_like(base, 255)
    raw = np.zeros((100, 120), dtype=np.uint8)
    raw[30:70, 40:80] = 255
    ok, encoded = cv2.imencode(".png", raw)
    assert ok
    mask = process_mask(encoded.tobytes(), (120, 100))
    result = feather_blend(base, source, mask, 8)
    assert result[50, 60, 0] > 240
    assert result[5, 5, 0] == 0
    assert 0 < result[30, 60, 0] < 255

