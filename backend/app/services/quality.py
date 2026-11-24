import cv2
import numpy as np


def boundary_difference(base: np.ndarray, result: np.ndarray, mask: np.ndarray) -> float:
    kernel = np.ones((7, 7), np.uint8)
    boundary = cv2.morphologyEx(mask, cv2.MORPH_GRADIENT, kernel)
    pixels = boundary > 0
    if not np.any(pixels):
        return 0.0
    lab_base = cv2.cvtColor(base, cv2.COLOR_BGR2LAB).astype(np.float32)
    lab_result = cv2.cvtColor(result, cv2.COLOR_BGR2LAB).astype(np.float32)
    return float(np.mean(np.linalg.norm(lab_base[pixels] - lab_result[pixels], axis=1)))

