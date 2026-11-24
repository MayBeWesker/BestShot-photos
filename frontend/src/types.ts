export type BlendMethod = 'feather' | 'poisson_normal' | 'poisson_mixed'
export type ToolMode = 'brush' | 'eraser'

export interface ImageInfo {
  width: number
  height: number
  format: string
  url: string
}

export interface AlignmentInfo {
  status: 'success' | 'failed'
  match_count: number
  inlier_count: number
  inlier_ratio: number
  reprojection_error: number | null
  valid_coverage: number
}

export interface VersionInfo {
  version: number
  parent_version: number | null
  result_url: string
  blend_mode: string
  local_alignment_success: boolean | null
  warnings: string[]
  created_at: string
}

export interface PhotoProject {
  id: string
  created_at: string
  main_image: ImageInfo
  source_image: ImageInfo
  alignment: AlignmentInfo | null
  versions: VersionInfo[]
  current_version: number
}

export interface ComposeResult {
  project_id: string
  version: number
  status: 'success'
  result_url: string
  local_alignment_success: boolean
  fallback_used: boolean
  warnings: string[]
}

export interface Stroke {
  id: string
  mode: ToolMode
  points: number[]
  width: number
}

export type GroupSensitivity = 'conservative' | 'standard' | 'loose'

export interface PhotoQuality {
  score: number
  sharpness: number
  exposure: number
  color: number
  composition: number
  simplicity?: number
  reasons: string[]
}

export interface OrganizedPhoto {
  id: string
  original_name: string
  width: number
  height: number
  taken_at: string | null
  image_url: string
  thumbnail_url: string
  quality: PhotoQuality
}

export interface PhotoGroup {
  id: string
  name: string
  photo_ids: string[]
}

export interface OrganizerProject {
  id: string
  created_at: string
  sensitivity: GroupSensitivity
  photos: OrganizedPhoto[]
  groups: PhotoGroup[]
}

export interface MomentsPhotoSelection {
  rank: number
  group_id: string
  photo_id: string
  reason: string
  role: string
}

export interface MomentsSelection {
  project_id: string
  model: string
  created_at: string
  story_title: string
  summary: string
  grid_review: string
  layout_rationale: string
  caption_suggestion: string
  analysis_candidate_count: number
  quality_threshold: number
  selected: MomentsPhotoSelection[]
}

export interface MomentsReplacement {
  group_id: string
  photo_id: string
  reason: string
  role: string
  grid_review: string
}

export type MomentsTone = '自然随性' | '简洁克制' | '活泼有趣' | '温柔文艺'

export interface MomentsContext {
  theme: string
  location: string
  highlights: string
  tone: MomentsTone
}

