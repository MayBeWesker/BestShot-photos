from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from typing import Literal

import cv2
import numpy as np
from PIL import Image, UnidentifiedImageError

from ..errors import BestShotError


Sensitivity = Literal["conservative", "standard", "loose"]


@dataclass
class PhotoFeatures:
    phash: np.ndarray
    visual: np.ndarray
    histogram: np.ndarray
    taken_at: datetime | None


@dataclass
class QualityResult:
    score: float
    sharpness: float
    exposure: float
    color: float
    composition: float
    simplicity: float
    reasons: list[str]


THRESHOLDS: dict[Sensitivity, float] = {
    "conservative": 0.79,
    "standard": 0.71,
    "loose": 0.64,
}


def extract_taken_at(data: bytes) -> datetime | None:
    """Read the original capture time without treating upload time as capture time."""
    try:
        with Image.open(BytesIO(data)) as image:
            exif = image.getexif()
            for tag in (36867, 36868, 306):
                value = exif.get(tag)
                if not value:
                    continue
                try:
                    return datetime.strptime(str(value), "%Y:%m:%d %H:%M:%S")
                except ValueError:
                    continue
    except (UnidentifiedImageError, OSError, ValueError):
        return None
    return None


def _unit(vector: np.ndarray) -> np.ndarray:
    vector = vector.astype(np.float32).reshape(-1)
    norm = float(np.linalg.norm(vector))
    return vector / norm if norm > 1e-8 else vector


def _phash(gray: np.ndarray) -> np.ndarray:
    small = cv2.resize(gray, (32, 32), interpolation=cv2.INTER_AREA).astype(np.float32)
    dct = cv2.dct(small)[:8, :8]
    values = dct.reshape(-1)
    median = float(np.median(values[1:]))
    return values > median


def extract_features(image: np.ndarray, taken_at: datetime | None = None) -> PhotoFeatures:
    preview = image
    height, width = preview.shape[:2]
    scale = min(1.0, 640.0 / max(height, width))
    if scale < 1:
        preview = cv2.resize(preview, (round(width * scale), round(height * scale)), interpolation=cv2.INTER_AREA)

    gray = cv2.cvtColor(preview, cv2.COLOR_BGR2GRAY)
    structure = cv2.resize(gray, (24, 24), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0
    structure -= float(np.mean(structure))
    edge = cv2.Canny(gray, 60, 150)
    edge_layout = cv2.resize(edge, (12, 12), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0
    visual = _unit(np.concatenate([structure.reshape(-1), edge_layout.reshape(-1) * 0.65]))

    hsv = cv2.cvtColor(preview, cv2.COLOR_BGR2HSV)
    histogram = cv2.calcHist([hsv], [0, 1], None, [18, 8], [0, 180, 0, 256])
    histogram = cv2.normalize(histogram, None, norm_type=cv2.NORM_L1).reshape(-1)
    return PhotoFeatures(_phash(gray), visual, histogram.astype(np.float32), taken_at)


def _cosine(left: np.ndarray, right: np.ndarray) -> float:
    denominator = float(np.linalg.norm(left) * np.linalg.norm(right))
    if denominator <= 1e-8:
        return 0.0
    return float(np.clip(np.dot(left, right) / denominator, -1.0, 1.0))


def photo_similarity(left: PhotoFeatures, right: PhotoFeatures) -> float:
    phash = 1.0 - float(np.count_nonzero(left.phash != right.phash)) / left.phash.size
    structure = (_cosine(left.visual, right.visual) + 1.0) / 2.0
    histogram = float(cv2.compareHist(left.histogram, right.histogram, cv2.HISTCMP_INTERSECT))
    histogram = float(np.clip(histogram, 0.0, 1.0))
    score = 0.48 * phash + 0.34 * structure + 0.18 * histogram

    if left.taken_at and right.taken_at:
        seconds = abs((left.taken_at - right.taken_at).total_seconds())
        if seconds <= 120:
            score += 0.055
        elif seconds <= 600:
            score += 0.025
        elif seconds > 7200:
            score -= 0.08
    return float(np.clip(score, 0.0, 1.0))


def cluster_photos(features: list[PhotoFeatures], sensitivity: Sensitivity = "standard") -> list[list[int]]:
    """Greedy complete-link grouping prevents A-B-C chain merges."""
    if sensitivity not in THRESHOLDS:
        raise BestShotError("分组灵敏度无效。", code="invalid_sensitivity")
    threshold = THRESHOLDS[sensitivity]
    groups: list[list[int]] = []

    order = sorted(
        range(len(features)),
        key=lambda index: (features[index].taken_at is None, features[index].taken_at or datetime.max, index),
    )
    for index in order:
        best_group: list[int] | None = None
        best_score = -1.0
        for group in groups:
            similarities = [photo_similarity(features[index], features[member]) for member in group]
            minimum = min(similarities)
            average = sum(similarities) / len(similarities)
            if minimum >= threshold and average > best_score:
                best_group = group
                best_score = average
        if best_group is None:
            groups.append([index])
        else:
            best_group.append(index)
    return groups


def score_quality(image: np.ndarray) -> QualityResult:
    height, width = image.shape[:2]
    scale = min(1.0, 1000.0 / max(height, width))
    preview = cv2.resize(image, (round(width * scale), round(height * scale)), interpolation=cv2.INTER_AREA) if scale < 1 else image
    gray = cv2.cvtColor(preview, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(preview, cv2.COLOR_BGR2HSV)

    laplacian_variance = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    sharpness = float(np.clip(np.log1p(laplacian_variance) / np.log(1201.0), 0.0, 1.0))

    luminance = gray.astype(np.float32) / 255.0
    mean_luminance = float(np.mean(luminance))
    clipped = float(np.mean((luminance < 0.025) | (luminance > 0.975)))
    exposure = float(np.clip(1.0 - abs(mean_luminance - 0.52) / 0.52 - clipped * 1.8, 0.0, 1.0))

    contrast = float(np.clip(np.std(luminance) / 0.24, 0.0, 1.0))
    saturation = float(np.mean(hsv[:, :, 1])) / 255.0
    color = float(np.clip(0.65 * contrast + 0.35 * (1.0 - abs(saturation - 0.42) / 0.58), 0.0, 1.0))

    edges = cv2.Canny(gray, 70, 160).astype(np.float32) / 255.0
    edge_density = float(np.mean(edges))
    gradient_x = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gradient_y = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    energy = cv2.magnitude(gradient_x, gradient_y) + 1e-6
    cell_energy = np.array([float(np.sum(cell)) for row in np.array_split(energy, 3, axis=0) for cell in np.array_split(row, 3, axis=1)])
    distribution = cell_energy / max(float(np.sum(cell_energy)), 1e-6)
    spatial_entropy = float(-np.sum(distribution * np.log(distribution + 1e-8)) / np.log(len(distribution)))
    concentration = float(np.clip((float(np.max(distribution)) - 1 / 9) / 0.34, 0.0, 1.0))

    y_coordinates, x_coordinates = np.indices(energy.shape)
    energy_sum = max(float(np.sum(energy)), 1e-6)
    focal_x = float(np.sum(x_coordinates * energy) / energy_sum) / max(energy.shape[1] - 1, 1)
    focal_y = float(np.sum(y_coordinates * energy) / energy_sum) / max(energy.shape[0] - 1, 1)
    thirds_distance = min(np.hypot(focal_x - x, focal_y - y) for x in (1 / 3, 2 / 3) for y in (1 / 3, 2 / 3))
    thirds_score = float(np.clip(1.0 - thirds_distance / 0.48, 0.0, 1.0))
    left = float(np.sum(energy[:, : energy.shape[1] // 2]))
    right = float(np.sum(energy[:, energy.shape[1] // 2 :]))
    balance = float(np.clip(1.0 - abs(left - right) / energy_sum * 1.8, 0.0, 1.0))
    composition = float(np.clip(0.38 * balance + 0.36 * concentration + 0.26 * thirds_score, 0.0, 1.0))

    # Dense edges spread evenly across the whole frame are a strong signal for
    # visual clutter. Unlike the previous score, more edges no longer mean a
    # better composition.
    busy_edges = float(np.clip((edge_density - 0.015) / 0.08, 0.0, 1.0))
    uniform_texture = float(np.clip((spatial_entropy - 0.62) / 0.38, 0.0, 1.0))
    simplicity = float(np.clip(1.0 - 0.65 * busy_edges - 0.35 * uniform_texture, 0.0, 1.0))

    # Fine texture can make a cluttered image look artificially "sharp" to a
    # Laplacian metric. Discount that false advantage without hiding the raw
    # sharpness sub-score shown to the user.
    aesthetic_sharpness = sharpness * (0.70 + 0.30 * simplicity)
    aesthetic_composition = composition * (0.65 + 0.35 * simplicity)

    score = 100.0 * (
        0.16 * aesthetic_sharpness
        + 0.18 * exposure
        + 0.13 * color
        + 0.23 * aesthetic_composition
        + 0.30 * simplicity
    )
    reasons: list[str] = []
    if sharpness >= 0.72:
        reasons.append("画面清晰")
    elif sharpness < 0.45:
        reasons.append("清晰度偏低")
    if exposure >= 0.78:
        reasons.append("曝光均衡")
    elif mean_luminance < 0.30:
        reasons.append("画面偏暗")
    elif mean_luminance > 0.75 or clipped > 0.12:
        reasons.append("高光偏多")
    if color >= 0.72:
        reasons.append("色彩层次良好")
    if composition >= 0.68:
        reasons.append("画面分布均衡")
    if simplicity >= 0.76:
        reasons.append("画面简洁")
    elif simplicity < 0.42:
        reasons.append("画面元素较多")
    if not reasons:
        reasons.append("综合质量一般")

    return QualityResult(
        score=round(score, 1),
        sharpness=round(sharpness * 100, 1),
        exposure=round(exposure * 100, 1),
        color=round(color * 100, 1),
        composition=round(composition * 100, 1),
        simplicity=round(simplicity * 100, 1),
        reasons=reasons,
    )
