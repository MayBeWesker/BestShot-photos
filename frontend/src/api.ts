import type { BlendMethod, ComposeResult, GroupSensitivity, MomentsContext, MomentsReplacement, MomentsSelection, OrganizerProject, PhotoProject } from './types'

export class ApiError extends Error {
  code: string

  constructor(message: string, code = 'request_failed') {
    super(message)
    this.code = code
  }
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init)
  if (!response.ok) {
    let message = `请求失败（${response.status}）`
    let code = 'request_failed'
    try {
      const body = await response.json()
      message = body?.error?.message ?? body?.detail ?? message
      code = body?.error?.code ?? code
    } catch {
      // Keep the HTTP fallback when the response is not JSON.
    }
    throw new ApiError(message, code)
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export async function createProject(main: File, source: File): Promise<PhotoProject> {
  const body = new FormData()
  body.append('main_image', main)
  body.append('source_image', source)
  return request('/api/projects', { method: 'POST', body })
}

export function alignProject(projectId: string): Promise<PhotoProject> {
  return request(`/api/projects/${projectId}/align`, { method: 'POST' })
}

export function getProject(projectId: string): Promise<PhotoProject> {
  return request(`/api/projects/${projectId}`)
}

export function activateVersion(projectId: string, version: number): Promise<PhotoProject> {
  return request(`/api/projects/${projectId}/versions/${version}/activate`, { method: 'POST' })
}

export async function composeProject(
  projectId: string,
  mask: Blob,
  options: { baseVersion: number; blendMethod: BlendMethod; featherRadius: number; useLocalAlignment: boolean },
): Promise<ComposeResult> {
  const body = new FormData()
  body.append('mask_file', mask, 'mask.png')
  body.append('base_version', String(options.baseVersion))
  body.append('blend_method', options.blendMethod)
  body.append('feather_radius', String(options.featherRadius))
  body.append('use_local_alignment', String(options.useLocalAlignment))
  return request(`/api/projects/${projectId}/compose`, { method: 'POST', body })
}

export function deleteProject(projectId: string): Promise<void> {
  return request(`/api/projects/${projectId}`, { method: 'DELETE' })
}

export function withCacheBust(url: string, key: string | number): string {
  return `${url}?v=${encodeURIComponent(String(key))}`
}

export async function createOrganizerProject(files: File[], sensitivity: GroupSensitivity): Promise<OrganizerProject> {
  const body = new FormData()
  files.forEach((file) => body.append('photos', file))
  body.append('sensitivity', sensitivity)
  return request('/api/organizer/projects', { method: 'POST', body })
}

export function deleteOrganizerProject(projectId: string): Promise<void> {
  return request(`/api/organizer/projects/${projectId}`, { method: 'DELETE' })
}

export function createMomentsSelection(projectId: string, context: MomentsContext): Promise<MomentsSelection> {
  return request(`/api/organizer/projects/${projectId}/moments-selection`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ context }),
  })
}

export async function downloadMomentsArchive(projectId: string, photoIds: string[]): Promise<Blob> {
  const response = await fetch(`/api/organizer/projects/${projectId}/moments-download`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ photo_ids: photoIds }),
  })
  if (!response.ok) {
    let message = `下载失败（${response.status}）`
    try {
      const body = await response.json()
      message = body?.error?.message ?? body?.detail ?? message
    } catch { /* Keep the HTTP fallback. */ }
    throw new ApiError(message, 'moments_download_failed')
  }
  return response.blob()
}

export function createMomentsReplacement(projectId: string, photoIds: string[], replaceRank: number): Promise<MomentsReplacement> {
  return request(`/api/organizer/projects/${projectId}/moments-replacement`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ photo_ids: photoIds, replace_rank: replaceRank }),
  })
}

