import cv2
import numpy as np

from ..errors import InvalidMaskError


def process_mask(data: bytes, expected_size: tuple[int, int], valid_mask: np.ndarray | None = None) -> np.ndarray:
    decoded = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
    if decoded is None:
        raise InvalidMaskError("无法读取遮罩 PNG。")
    if decoded.ndim == 3:
        if decoded.shape[2] == 4:
            decoded = cv2.cvtColor(decoded[:, :, :3], cv2.COLOR_BGR2GRAY)
        else:
            decoded = cv2.cvtColor(decoded, cv2.COLOR_BGR2GRAY)
    width, height = expected_size
    if decoded.shape[:2] != (height, width):
        raise InvalidMaskError(f"遮罩尺寸必须与主图一致（{width}×{height}）。")
    _, binary = cv2.threshold(decoded, 32, 255, cv2.THRESH_BINARY)
    kernel = np.ones((3, 3), np.uint8)
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=1)
    if valid_mask is not None:
        binary = cv2.bitwise_and(binary, valid_mask)
    area = int(np.count_nonzero(binary))
    if area < 64:
        raise InvalidMaskError("涂抹区域太小，请扩大需要替换的范围。")
    if area > binary.size * 0.75:
        raise InvalidMaskError("一次替换区域不能超过整张照片的 75%。")
    return binary


def mask_bounds(mask: np.ndarray, padding: int = 80) -> tuple[int, int, int, int]:
    points = cv2.findNonZero(mask)
    if points is None:
        raise InvalidMaskError("遮罩中没有有效区域。")
    x, y, width, height = cv2.boundingRect(points)
    image_height, image_width = mask.shape
    return (
        max(0, x - padding),
        max(0, y - padding),
        min(image_width, x + width + padding),
        min(image_height, y + height + padding),
    )

