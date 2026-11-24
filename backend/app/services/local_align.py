from dataclasses import dataclass
import math

import cv2
import numpy as np

from .mask import mask_bounds


@dataclass
class LocalAlignmentResult:
    image: np.ndarray
    success: bool
    warning: str | None = None
    tracked_points: int = 0
    residual: float | None = None


def align_local(base: np.ndarray, aligned_source: np.ndarray, mask: np.ndarray) -> LocalAlignmentResult:
    x1, y1, x2, y2 = mask_bounds(mask, padding=max(48, int(max(mask.shape) * 0.025)))
    source_gray = cv2.cvtColor(aligned_source, cv2.COLOR_BGR2GRAY)
    base_gray = cv2.cvtColor(base, cv2.COLOR_BGR2GRAY)
    roi_source = source_gray[y1:y2, x1:x2]

    features = cv2.goodFeaturesToTrack(
        roi_source,
        maxCorners=500,
        qualityLevel=0.015,
        minDistance=7,
        blockSize=7,
    )
    if features is None or len(features) < 12:
        return LocalAlignmentResult(aligned_source, False, "局部纹理不足，已回退到全局配准结果。")
    features[:, 0, 0] += x1
    features[:, 0, 1] += y1

    next_points, status_fwd, _ = cv2.calcOpticalFlowPyrLK(
        source_gray, base_gray, features, None, winSize=(31, 31), maxLevel=4,
        criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 40, 0.01),
    )
    if next_points is None:
        return LocalAlignmentResult(aligned_source, False, "局部光流跟踪失败，已回退到全局配准结果。")
    back_points, status_back, _ = cv2.calcOpticalFlowPyrLK(
        base_gray, source_gray, next_points, None, winSize=(31, 31), maxLevel=4,
        criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 40, 0.01),
    )
    if back_points is None:
        return LocalAlignmentResult(aligned_source, False, "局部光流一致性检查失败，已回退到全局配准结果。")

    fb_error = np.linalg.norm(features - back_points, axis=2).ravel()
    valid = status_fwd.ravel().astype(bool) & status_back.ravel().astype(bool) & (fb_error < 1.8)
    src = features[valid].reshape(-1, 2)
    dst = next_points[valid].reshape(-1, 2)
    if len(src) < 10:
        return LocalAlignmentResult(aligned_source, False, "可靠的局部匹配点不足，已回退到全局配准结果。", len(src))

    matrix, inliers = cv2.estimateAffinePartial2D(src, dst, method=cv2.RANSAC, ransacReprojThreshold=3.0, maxIters=3000, confidence=0.995)
    if matrix is None or inliers is None or int(inliers.sum()) < 8:
        return LocalAlignmentResult(aligned_source, False, "无法估计稳定的局部变换，已回退到全局配准结果。", len(src))

    a, b, tx = matrix[0]
    c, d, ty = matrix[1]
    scale = math.sqrt(a * a + c * c)
    rotation = abs(math.degrees(math.atan2(c, a)))
    translation = math.hypot(tx, ty)
    if not (0.93 <= scale <= 1.07) or rotation > 5.0 or translation > max(80.0, 0.08 * max(x2 - x1, y2 - y1)):
        return LocalAlignmentResult(aligned_source, False, "局部变换幅度异常，已回退到更安全的全局配准结果。", len(src))

    inlier_bool = inliers.ravel().astype(bool)
    predicted = cv2.transform(src[inlier_bool].reshape(-1, 1, 2), matrix).reshape(-1, 2)
    residual = float(np.median(np.linalg.norm(predicted - dst[inlier_bool], axis=1)))
    if residual > 3.5:
        return LocalAlignmentResult(aligned_source, False, "局部对齐残差过大，已回退到全局配准结果。", len(src), residual)

    height, width = aligned_source.shape[:2]
    warped = cv2.warpAffine(aligned_source, matrix, (width, height), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
    return LocalAlignmentResult(warped, True, tracked_points=int(inlier_bool.sum()), residual=residual)

