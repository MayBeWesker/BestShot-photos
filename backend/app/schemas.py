from typing import Literal
from pydantic import BaseModel, Field


class ImageInfo(BaseModel):
    width: int
    height: int
    format: str
    url: str


class AlignmentInfo(BaseModel):
    status: Literal["success", "failed"]
    homography: list[list[float]] | None = None
    match_count: int = 0
    inlier_count: int = 0
    inlier_ratio: float = 0
    reprojection_error: float | None = None
    valid_coverage: float = 0


class VersionInfo(BaseModel):
    version: int
    parent_version: int | None
    result_url: str
    blend_mode: str
    local_alignment_success: bool | None
    warnings: list[str] = Field(default_factory=list)
    created_at: str


class ProjectResponse(BaseModel):
    id: str
    created_at: str
    main_image: ImageInfo
    source_image: ImageInfo
    alignment: AlignmentInfo | None = None
    versions: list[VersionInfo]
    current_version: int


class ComposeResponse(BaseModel):
    project_id: str
    version: int
    status: Literal["success"] = "success"
    result_url: str
    local_alignment_success: bool
    fallback_used: bool
    warnings: list[str] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: str = "bestshot-photos"


class QualityScore(BaseModel):
    score: float
    sharpness: float
    exposure: float
    color: float
    composition: float
    simplicity: float = 0
    reasons: list[str]


class OrganizedPhoto(BaseModel):
    id: str
    original_name: str
    width: int
    height: int
    taken_at: str | None
    image_url: str
    thumbnail_url: str
    quality: QualityScore


class PhotoGroup(BaseModel):
    id: str
    name: str
    photo_ids: list[str]


class OrganizerProjectResponse(BaseModel):
    id: str
    created_at: str
    sensitivity: Literal["conservative", "standard", "loose"]
    photos: list[OrganizedPhoto]
    groups: list[PhotoGroup]


class MomentsPhotoSelection(BaseModel):
    rank: int = Field(ge=1, le=9)
    group_id: str = Field(max_length=80)
    photo_id: str = Field(max_length=80)
    reason: str = Field(max_length=200)
    role: str = Field(max_length=40)


class MomentsSelectionContext(BaseModel):
    theme: str = Field(default="", max_length=120)
    location: str = Field(default="", max_length=120)
    highlights: str = Field(default="", max_length=1200)
    tone: Literal["自然随性", "简洁克制", "活泼有趣", "温柔文艺"] = "自然随性"


class MomentsSelectionRequest(BaseModel):
    context: MomentsSelectionContext = Field(default_factory=MomentsSelectionContext)


class MomentsDownloadRequest(BaseModel):
    photo_ids: list[str] = Field(min_length=1, max_length=9)


class MomentsReplacementRequest(BaseModel):
    photo_ids: list[str] = Field(min_length=1, max_length=9)
    replace_rank: int = Field(ge=1, le=9)


class MomentsReplacementResponse(BaseModel):
    group_id: str
    photo_id: str
    reason: str
    role: str
    grid_review: str


class MomentsSelectionResponse(BaseModel):
    project_id: str = Field(max_length=120)
    model: str = Field(max_length=120)
    created_at: str = Field(max_length=80)
    story_title: str = Field(max_length=120)
    summary: str = Field(max_length=500)
    grid_review: str = Field(max_length=800)
    layout_rationale: str = Field(max_length=800)
    caption_suggestion: str = Field(max_length=500)
    analysis_candidate_count: int = Field(ge=1, le=60)
    quality_threshold: float = Field(ge=0, le=100)
    selected: list[MomentsPhotoSelection] = Field(min_length=1, max_length=9)


class MomentsRegenerationRequest(BaseModel):
    instruction: str = Field(default="", max_length=800)
    previous: MomentsSelectionResponse

