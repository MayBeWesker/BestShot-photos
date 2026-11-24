import cv2
import numpy as np

from ..errors import InvalidMaskError


def feather_blend(base: np.ndarray, source: np.ndarray, mask: np.ndarray, radius: int) -> np.ndarray:
    radius = max(1, min(int(radius), 80))
    kernel = radius * 2 + 1
    alpha = cv2.GaussianBlur(mask.astype(np.float32) / 255.0, (kernel, kernel), sigmaX=max(1, radius / 2))
    alpha = alpha[:, :, None]
    result = source.astype(np.float32) * alpha + base.astype(np.float32) * (1.0 - alpha)
    return np.clip(result, 0, 255).astype(np.uint8)


def poisson_blend(base: np.ndarray, source: np.ndarray, mask: np.ndarray, mixed: bool = False) -> np.ndarray:
    points = cv2.findNonZero(mask)
    if points is None:
        raise InvalidMaskError("遮罩中没有有效区域。")
    x, y, width, height = cv2.boundingRect(points)
    center = (x + width // 2, y + height // 2)
    mode = cv2.MIXED_CLONE if mixed else cv2.NORMAL_CLONE
    try:
        return cv2.seamlessClone(source, base, mask, center, mode)
    except cv2.error as exc:
        raise InvalidMaskError("Poisson 融合失败；请缩小区域或改用羽化融合。") from exc


def blend_images(base: np.ndarray, source: np.ndarray, mask: np.ndarray, method: str, feather_radius: int) -> np.ndarray:
    if method == "feather":
        return feather_blend(base, source, mask, feather_radius)
    if method == "poisson_normal":
        return poisson_blend(base, source, mask, mixed=False)
    if method == "poisson_mixed":
        return poisson_blend(base, source, mask, mixed=True)
    raise InvalidMaskError("未知的融合方式。")

