from dataclasses import dataclass, field

import numpy as np

from .blending import blend_images
from .local_align import align_local
from .quality import boundary_difference


@dataclass
class ComposeResult:
    image: np.ndarray
    local_alignment_success: bool
    fallback_used: bool
    warnings: list[str] = field(default_factory=list)


def compose(
    base: np.ndarray,
    aligned_source: np.ndarray,
    mask: np.ndarray,
    *,
    use_local_alignment: bool,
    blend_method: str,
    feather_radius: int,
) -> ComposeResult:
    warnings: list[str] = []
    source_for_blend = aligned_source
    local_success = False
    fallback_used = False
    if use_local_alignment:
        local = align_local(base, aligned_source, mask)
        source_for_blend = local.image
        local_success = local.success
        if local.warning:
            warnings.append(local.warning)
        fallback_used = not local.success
    result = blend_images(base, source_for_blend, mask, blend_method, feather_radius)
    seam_score = boundary_difference(base, result, mask)
    if seam_score > 28:
        warnings.append("检测到替换边缘的色差较明显，可尝试增大羽化半径或切换 Poisson 融合。")
    return ComposeResult(result, local_success, fallback_used, warnings)

