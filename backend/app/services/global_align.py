from dataclasses import dataclass

import cv2
import numpy as np

from ..config import WORKING_MAX_EDGE
from ..errors import AlignmentError


@dataclass
class GlobalAlignmentResult:
    aligned: np.ndarray
    valid_mask: np.ndarray
    homography: np.ndarray
    match_count: int
    inlier_count: int
    inlier_ratio: float
    reprojection_error: float
    valid_coverage: float


def _working_image(image: np.ndarray) -> tuple[np.ndarray, float]:
    height, width = image.shape[:2]
    scale = min(1.0, WORKING_MAX_EDGE / max(width, height))
    if scale == 1.0:
        return image, scale
    resized = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    return resized, scale


def _detect(gray: np.ndarray) -> tuple[list[cv2.KeyPoint], np.ndarray | None]:
    sift = cv2.SIFT_create(nfeatures=7000, contrastThreshold=0.025, edgeThreshold=12)
    return sift.detectAndCompute(gray, None)


def align_global(main: np.ndarray, source: np.ndarray) -> GlobalAlignmentResult:
    main_work, main_scale = _working_image(main)
    source_work, source_scale = _working_image(source)
    main_gray = cv2.cvtColor(main_work, cv2.COLOR_BGR2GRAY)
    source_gray = cv2.cvtColor(source_work, cv2.COLOR_BGR2GRAY)

    kp_main, desc_main = _detect(main_gray)
    kp_source, desc_source = _detect(source_gray)
    if desc_main is None or desc_source is None or len(kp_main) < 12 or len(kp_source) < 12:
        raise AlignmentError("照片中的可识别特征太少，无法完成自动配准。")

    matcher = cv2.BFMatcher(cv2.NORM_L2)
    pairs = matcher.knnMatch(desc_source, desc_main, k=2)
    good = [first for first, second in pairs if first.distance < 0.72 * second.distance]
    if len(good) < 12:
        raise AlignmentError(f"两张照片只有 {len(good)} 个可靠匹配点，请选择同一机位连续拍摄的照片。")

    source_points = np.float32([kp_source[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
    main_points = np.float32([kp_main[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
    work_h, inliers = cv2.findHomography(source_points, main_points, cv2.RANSAC, 4.0, maxIters=5000, confidence=0.997)
    if work_h is None or inliers is None:
        raise AlignmentError("RANSAC 无法估计稳定的照片变换。")

    inlier_mask = inliers.ravel().astype(bool)
    inlier_count = int(inlier_mask.sum())
    inlier_ratio = inlier_count / len(good)
    if inlier_count < 10 or inlier_ratio < 0.25:
        raise AlignmentError("照片匹配不稳定；请使用背景和构图更接近的两张照片。")

    projected = cv2.perspectiveTransform(source_points[inlier_mask], work_h)
    errors = np.linalg.norm(projected - main_points[inlier_mask], axis=2).ravel()
    reprojection_error = float(np.median(errors) / main_scale)
    if reprojection_error > 10:
        raise AlignmentError("自动配准误差过大，继续合成可能产生明显重影。")

    scale_source = np.diag([source_scale, source_scale, 1.0])
    scale_main_inv = np.diag([1.0 / main_scale, 1.0 / main_scale, 1.0])
    homography = scale_main_inv @ work_h @ scale_source
    height, width = main.shape[:2]
    aligned = cv2.warpPerspective(source, homography, (width, height), flags=cv2.INTER_LINEAR)
    source_valid = np.full(source.shape[:2], 255, dtype=np.uint8)
    valid_mask = cv2.warpPerspective(source_valid, homography, (width, height), flags=cv2.INTER_NEAREST)
    valid_coverage = float(np.count_nonzero(valid_mask) / valid_mask.size)
    if valid_coverage < 0.25:
        raise AlignmentError("素材图映射后的有效覆盖范围过小。")

    return GlobalAlignmentResult(
        aligned=aligned,
        valid_mask=valid_mask,
        homography=homography,
        match_count=len(good),
        inlier_count=inlier_count,
        inlier_ratio=float(inlier_ratio),
        reprojection_error=reprojection_error,
        valid_coverage=valid_coverage,
    )

