import { useEffect, useMemo, useRef, useState } from 'react'
import { ArrowLeft, Bot, Check, ChevronRight, Copy, Download, Images, LoaderCircle, LockKeyhole, Medal, Plus, RefreshCw, Sparkles, Trash2, UploadCloud, WandSparkles, X } from 'lucide-react'
import { createMomentsReplacement, createMomentsSelection, createOrganizerProject, deleteOrganizerProject, downloadMomentsArchive } from '../api'
import type { GroupSensitivity, MomentsContext, MomentsSelection, MomentsTone, OrganizerProject, PhotoGroup } from '../types'

interface Props {
  onError: (message: string) => void
  onActiveChange: (active: boolean) => void
}

const modes: { value: GroupSensitivity; label: string; description: string }[] = [
  { value: 'conservative', label: '保守', description: '宁可多分组，减少误合并' },
  { value: 'standard', label: '标准', description: '适合大多数旅行相册' },
  { value: 'loose', label: '宽松', description: '合并更多相近构图' },
]

export function PhotoOrganizer({ onError, onActiveChange }: Props) {
  const [files, setFiles] = useState<File[]>([])
  const [sensitivity, setSensitivity] = useState<GroupSensitivity>('standard')
  const [project, setProject] = useState<OrganizerProject | null>(null)
  const [selectedGroupId, setSelectedGroupId] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const previews = useMemo(() => files.slice(0, 8).map((file, index) => ({ file, index, url: URL.createObjectURL(file) })), [files])
  useEffect(() => () => previews.forEach((item) => URL.revokeObjectURL(item.url)), [previews])

  const addFiles = (incoming: FileList | File[]) => {
    const accepted = Array.from(incoming).filter((file) =>
      /image\/(jpeg|png|webp|heic|heif)/i.test(file.type) || /\.(jpe?g|png|webp|heic|heif)$/i.test(file.name),
    )
    setFiles((current) => {
      const next = [...current, ...accepted]
      if (next.length > 200) onError('单次最多处理 200 张照片。')
      return next.slice(0, 200)
    })
  }

  const removeFile = (index: number) => {
    if (loading) return
    setFiles((current) => current.filter((_, currentIndex) => currentIndex !== index))
  }

  const clearFiles = () => {
    if (loading) return
    setFiles([])
    if (inputRef.current) inputRef.current.value = ''
  }

  const analyze = async () => {
    if (files.length < 2) return
    try {
      setLoading(true)
      const result = await createOrganizerProject(files, sensitivity)
      setProject(result)
      onActiveChange(true)
      setSelectedGroupId(result.groups[0]?.id ?? null)
    } catch (reason) {
      onError(reason instanceof Error ? reason.message : '照片分析失败。')
    } finally {
      setLoading(false)
    }
  }

  const reset = async () => {
    const current = project
    setProject(null)
    onActiveChange(false)
    setSelectedGroupId(null)
    setFiles([])
    if (current) {
      try { await deleteOrganizerProject(current.id) } catch { /* Local cleanup is best effort. */ }
    }
  }

  if (project) {
    const selected = project.groups.find((group) => group.id === selectedGroupId) ?? project.groups[0]
    return <OrganizerResults project={project} selected={selected} onSelect={setSelectedGroupId} onReset={reset} onError={onError} />
  }

  return (
    <main className="organizer-upload">
      <section className="organizer-intro">
        <div className="eyebrow"><span /> AI PHOTO ORGANIZER</div>
        <h1>只管记录精彩，<br />剩下的交给 <em>AI</em></h1>
        <p>自动分组、智能排序，再把旅途中真正值得分享的照片挑出来。</p>
        <div className="organizer-feature-list">
          <div><Check size={15} /><strong>相似场景自动归组</strong></div>
          <div><Medal size={15} /><strong>好照片优先展示</strong></div>
          <div><LockKeyhole size={15} /><strong>原图保留在本地</strong></div>
        </div>
      </section>

      <section className="batch-card">
        <div className="batch-card-heading">
          <div><small>ADD PHOTOS</small><h2>选择旅行照片</h2></div>
          <span>已选 {files.length} / 200</span>
        </div>
        <div
          className={`batch-dropzone ${files.length ? 'has-files' : ''}`}
          role="button"
          tabIndex={0}
          onClick={() => inputRef.current?.click()}
          onKeyDown={(event) => { if (event.key === 'Enter' || event.key === ' ') inputRef.current?.click() }}
          onDragOver={(event) => event.preventDefault()}
          onDrop={(event) => { event.preventDefault(); addFiles(event.dataTransfer.files) }}
        >
          <input ref={inputRef} type="file" accept="image/jpeg,image/png,image/webp,image/heic,image/heif,.jpg,.jpeg,.png,.webp,.heic,.heif" multiple hidden onChange={(event) => { if (event.target.files) addFiles(event.target.files); event.currentTarget.value = '' }} />
          {files.length ? (
            <div className="preview-mosaic">
              {previews.map(({ file, index, url }) => /\.(heic|heif)$/i.test(file.name)
                ? <div className="heic-preview" key={`${file.name}-${file.lastModified}-${index}`}><Images size={20} /><strong>HEIC</strong><small>{file.name}</small></div>
                : <img key={`${file.name}-${file.lastModified}-${index}`} src={url} alt="" />)}
              {files.length > 8 && <span>+{files.length - 8}</span>}
              <i><Plus size={17} />继续添加</i>
            </div>
          ) : (
            <div className="dropzone-empty"><UploadCloud size={32} /><strong>拖放照片到这里</strong><span>或点击浏览 · 支持 JPG、PNG、WebP、HEIC / HEIF · 最多 200 张</span></div>
          )}
        </div>

        {files.length > 0 && (
          <div className="selected-files">
            <div className="selected-files-heading">
              <span>已选择 {files.length} 张照片</span>
              <button type="button" disabled={loading} onClick={clearFiles}><Trash2 size={12} />清空全部</button>
            </div>
            <div className="selected-files-list">
              {files.map((file, index) => (
                <div className="selected-file" key={`${file.name}-${file.size}-${file.lastModified}-${index}`}>
                  <span className="selected-file-format">{file.name.split('.').pop()?.toUpperCase() || 'IMAGE'}</span>
                  <span title={file.name}>{file.name}<small>{formatFileSize(file.size)}</small></span>
                  <button type="button" disabled={loading} aria-label={`删除 ${file.name}`} title="从本次上传中删除" onClick={() => removeFile(index)}><Trash2 size={14} /></button>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="sensitivity-row">
          <label>分组灵敏度</label>
          <div className="sensitivity-options">
            {modes.map((mode) => (
              <button key={mode.value} type="button" className={sensitivity === mode.value ? 'active' : ''} onClick={() => setSensitivity(mode.value)} title={mode.description}>{mode.label}</button>
            ))}
          </div>
        </div>
        <button className="primary-action" type="button" disabled={files.length < 2 || loading} onClick={analyze}>
          {loading ? <><LoaderCircle className="spin" size={17} />正在分析 {files.length} 张照片…</> : <><Sparkles size={16} />开始智能整理<ChevronRight size={16} /></>}
        </button>
        <p className="upload-tip">首版使用 CPU 本地分析，照片较多时请耐心等待</p>
      </section>
    </main>
  )
}

function OrganizerResults({ project, selected, onSelect, onReset, onError }: { project: OrganizerProject; selected?: PhotoGroup; onSelect: (id: string) => void; onReset: () => void; onError: (message: string) => void }) {
  const [moments, setMoments] = useState<MomentsSelection | null>(null)
  const [selectingMoments, setSelectingMoments] = useState(false)
  const [downloadingMoments, setDownloadingMoments] = useState(false)
  const [smartReplacingRank, setSmartReplacingRank] = useState<number | null>(null)
  const [contextDialogOpen, setContextDialogOpen] = useState(false)
  const byId = new Map(project.photos.map((photo) => [photo.id, photo]))
  const selectedPhotos = (selected?.photo_ids ?? []).map((id) => byId.get(id)).filter(Boolean) as OrganizerProject['photos']

  const selectForMoments = async (context: MomentsContext) => {
    try {
      setSelectingMoments(true)
      setMoments(await createMomentsSelection(project.id, context))
      setContextDialogOpen(false)
    } catch (reason) {
      onError(reason instanceof Error ? reason.message : '九图生成失败。')
    } finally {
      setSelectingMoments(false)
    }
  }

  const replaceMomentGroup = (rank: number, groupId: string, photoId: string, reason: string, role = '故事补充', gridReview?: string) => {
    setMoments((current) => current ? {
      ...current,
      grid_review: gridReview ?? `你已手动更换第 ${rank} 格的分组；当前九图已更新，可继续调整或使用智能换组再次复核。`,
      selected: current.selected.map((item) => item.rank === rank ? { ...item, group_id: groupId, photo_id: photoId, reason, role } : item),
    } : current)
  }

  const smartReplaceMoment = async (rank: number) => {
    if (!moments) return
    try {
      setSmartReplacingRank(rank)
      const replacement = await createMomentsReplacement(project.id, moments.selected.map((item) => item.photo_id), rank)
      replaceMomentGroup(rank, replacement.group_id, replacement.photo_id, replacement.reason, replacement.role, replacement.grid_review)
    } catch (reason) {
      onError(reason instanceof Error ? reason.message : '智能换组失败。')
    } finally {
      setSmartReplacingRank(null)
    }
  }

  const downloadMoments = async () => {
    if (!moments) return
    try {
      setDownloadingMoments(true)
      const blob = await downloadMomentsArchive(project.id, moments.selected.map((item) => item.photo_id))
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = 'BestShot-朋友圈九图.zip'
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch (reason) {
      onError(reason instanceof Error ? reason.message : '九图下载失败。')
    } finally {
      setDownloadingMoments(false)
    }
  }

  return (
    <main className="organizer-results">
      <header className="results-header">
        <div className="brand"><span className="brand-mark"><Sparkles size={17} /></span><span><strong>BestShot</strong><small>ORGANIZER</small></span></div>
        <div className="results-summary"><strong>{project.photos.length}</strong> 张照片 <i /> <strong>{project.groups.length}</strong> 个场景 <i /> 已按质量排序</div>
        <div className="results-actions">
          <button className="moments-button" type="button" disabled={selectingMoments} onClick={() => setContextDialogOpen(true)} title="从各分组的高分代表图中生成朋友圈九图">
            {selectingMoments ? <LoaderCircle className="spin" size={14} /> : <Bot size={14} />}{selectingMoments ? '正在构建…' : '生成朋友圈'}
          </button>
          <button className="quiet-button" type="button" onClick={onReset}><ArrowLeft size={14} />重新选择</button>
        </div>
      </header>
      <div className="organizer-workspace">
        <aside className="group-sidebar">
          <div className="group-sidebar-title"><span>照片分组</span><small>{project.groups.length} GROUPS</small></div>
          <div className="group-list">
            {project.groups.map((group) => {
              const cover = byId.get(group.photo_ids[0])
              return (
                <button key={group.id} className={selected?.id === group.id ? 'active' : ''} type="button" onClick={() => onSelect(group.id)}>
                  {cover && <img src={cover.thumbnail_url} alt="" />}
                  <span><strong>{group.name}</strong><small>{group.photo_ids.length} 张 · 最高 {cover?.quality.score ?? 0} 分</small></span>
                  <ChevronRight size={14} />
                </button>
              )
            })}
          </div>
        </aside>
        <section className="photo-group-view">
          {moments && <MomentsResult selection={moments} project={project} downloading={downloadingMoments} smartReplacingRank={smartReplacingRank} onDownload={downloadMoments} onReplace={replaceMomentGroup} onSmartReplace={smartReplaceMoment} />}
          <div className="group-view-heading">
            <div><span className="live-dot" /><div><h1>{selected?.name}</h1><p>已按综合质量从高到低排列</p></div></div>
            <span className="local-badge"><i /> LOCAL ANALYSIS</span>
          </div>
          <div className="quality-grid">
            {selectedPhotos.map((photo, index) => (
              <article className={`quality-card ${index === 0 ? 'best' : ''}`} key={photo.id}>
                <a href={photo.image_url} target="_blank" rel="noreferrer" className="quality-image">
                  <img src={photo.thumbnail_url} alt={photo.original_name} />
                  <span className="rank">#{index + 1}</span>
                  {index === 0 && <span className="best-badge"><Medal size={13} />本组最佳</span>}
                </a>
                <div className="quality-info">
                  <div className="quality-score"><strong>{photo.quality.score}</strong><span>/ 100<small>综合质量</small></span></div>
                  <p>{photo.quality.reasons.join(' · ')}</p>
                  <div className="metric-grid">
                    <Metric label="清晰" value={photo.quality.sharpness} />
                    <Metric label="曝光" value={photo.quality.exposure} />
                    <Metric label="色彩" value={photo.quality.color} />
                    <Metric label="构图" value={photo.quality.composition} />
                    {photo.quality.simplicity !== undefined && <Metric label="简洁" value={photo.quality.simplicity} />}
                  </div>
                  <footer title={photo.original_name}><Images size={12} />{photo.original_name}<span>{photo.width} × {photo.height}</span></footer>
                </div>
              </article>
            ))}
          </div>
        </section>
      </div>
      {contextDialogOpen && <MomentsContextDialog loading={selectingMoments} onClose={() => setContextDialogOpen(false)} onGenerate={selectForMoments} />}
    </main>
  )
}

const momentsTones: MomentsTone[] = ['自然随性', '简洁克制', '活泼有趣', '温柔文艺']
const momentsContextStorageKey = 'bestshot.moments-context.v1'
const defaultMomentsContext: MomentsContext = { theme: '', location: '', highlights: '', tone: '自然随性' }

function loadMomentsContext(): MomentsContext {
  try {
    const saved = JSON.parse(window.localStorage.getItem(momentsContextStorageKey) ?? '{}') as Partial<MomentsContext>
    return {
      theme: typeof saved.theme === 'string' ? saved.theme.slice(0, 120) : '',
      location: typeof saved.location === 'string' ? saved.location.slice(0, 120) : '',
      highlights: typeof saved.highlights === 'string' ? saved.highlights.slice(0, 1200) : '',
      tone: momentsTones.includes(saved.tone as MomentsTone) ? saved.tone as MomentsTone : '自然随性',
    }
  } catch {
    return defaultMomentsContext
  }
}

function MomentsContextDialog({ loading, onClose, onGenerate }: { loading: boolean; onClose: () => void; onGenerate: (context: MomentsContext) => void }) {
  const [context, setContext] = useState<MomentsContext>(loadMomentsContext)
  const update = (key: keyof MomentsContext, value: string) => setContext((current) => ({ ...current, [key]: value }))
  const submit = () => {
    try { window.localStorage.setItem(momentsContextStorageKey, JSON.stringify(context)) } catch { /* Browser storage may be unavailable in privacy mode. */ }
    onGenerate(context)
  }
  return (
    <div className="dialog-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget && !loading) onClose() }}>
      <form className="moments-dialog" role="dialog" aria-modal="true" aria-labelledby="moments-dialog-title" onSubmit={(event) => { event.preventDefault(); submit() }}>
        <header><div><span><Bot size={18} /></span><div><h2 id="moments-dialog-title">补充朋友圈背景（可选）</h2></div></div><button type="button" disabled={loading} onClick={onClose} aria-label="关闭"><X size={17} /></button></header>
        <div className="dialog-fields">
          <label><span>主题</span><input value={context.theme} maxLength={120} onChange={(event) => update('theme', event.target.value)} placeholder="例如：秋日旅行" /></label>
          <label><span>地点</span><input value={context.location} maxLength={120} onChange={(event) => update('location', event.target.value)} placeholder="例如：京都" /></label>
          <label className="wide"><span>想记录的故事或心情</span><textarea value={context.highlights} maxLength={1200} rows={3} onChange={(event) => update('highlights', event.target.value)} placeholder="例如：希望多选风景，整体轻松自然" /></label>
          <label className="wide"><span>文案风格</span><div className="tone-options">{momentsTones.map((tone) => <button type="button" key={tone} className={context.tone === tone ? 'active' : ''} onClick={() => update('tone', tone)}>{tone}</button>)}</div></label>
        </div>
        <p className="dialog-data-note"><LockKeyhole size={13} />仅分析达到质量门槛的分组代表图</p>
        <footer><button type="button" className="dialog-skip" disabled={loading} onClick={() => onGenerate(defaultMomentsContext)}>跳过</button><button type="submit" className="dialog-generate" disabled={loading}>{loading ? <LoaderCircle className="spin" size={15} /> : <Sparkles size={15} />}{loading ? '正在分析…' : '生成朋友圈'}</button></footer>
      </form>
    </div>
  )
}

function MomentsResult({ selection, project, downloading, smartReplacingRank, onDownload, onReplace, onSmartReplace }: { selection: MomentsSelection; project: OrganizerProject; downloading: boolean; smartReplacingRank: number | null; onDownload: () => void; onReplace: (rank: number, groupId: string, photoId: string, reason: string, role?: string, gridReview?: string) => void; onSmartReplace: (rank: number) => Promise<void> }) {
  const [manualReplaceRank, setManualReplaceRank] = useState<number | null>(null)
  const [activeMenuRank, setActiveMenuRank] = useState<number | null>(null)
  const [captionCopied, setCaptionCopied] = useState(false)
  const byId = new Map(project.photos.map((photo) => [photo.id, photo]))
  const groupsById = new Map(project.groups.map((group) => [group.id, group]))
  const usedGroupIds = new Set(selection.selected.map((item) => item.group_id))
  const availableGroups = project.groups.filter((group) => !usedGroupIds.has(group.id))
  const copyCaption = async () => {
    try {
      await navigator.clipboard.writeText(selection.caption_suggestion)
    } catch {
      const textarea = document.createElement('textarea')
      textarea.value = selection.caption_suggestion
      textarea.style.position = 'fixed'
      textarea.style.opacity = '0'
      document.body.appendChild(textarea)
      textarea.select()
      document.execCommand('copy')
      textarea.remove()
    }
    setCaptionCopied(true)
    window.setTimeout(() => setCaptionCopied(false), 1800)
  }
  return (
    <section className="moments-result">
      <div className="moments-heading">
        <div><span><Bot size={17} /></span><div><small>朋友圈九图</small><h2>{selection.story_title}</h2></div></div>
        <div className="moments-heading-actions"><span>{selection.analysis_candidate_count} 张候选 · {selection.quality_threshold} 分门槛</span><button type="button" disabled={downloading} onClick={onDownload}>{downloading ? <LoaderCircle className="spin" size={15} /> : <Download size={15} />}{downloading ? '正在打包…' : '下载九图'}</button></div>
      </div>
      <div className="moments-caption moments-caption-top"><div><small>朋友圈文案</small><button type="button" onClick={copyCaption}>{captionCopied ? <Check size={15} /> : <Copy size={15} />}{captionCopied ? '已复制' : '复制文案'}</button></div><p>{selection.caption_suggestion}</p></div>
      <p className="moments-summary">{selection.summary}</p>
      <div className="moments-main-layout">
        <div className="moments-grid">
          {selection.selected.map((item) => {
            const photo = byId.get(item.photo_id)
            if (!photo) return null
            const replacing = smartReplacingRank === item.rank
            const menuOpen = activeMenuRank === item.rank
            return (
              <div className={`moments-tile ${menuOpen ? 'menu-open' : ''}`} role="button" tabIndex={0} key={item.rank} onClick={() => setActiveMenuRank(menuOpen ? null : item.rank)} onKeyDown={(event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); setActiveMenuRank(menuOpen ? null : item.rank) } }} aria-expanded={menuOpen} aria-label={`调整第 ${item.rank} 格：${photo.original_name}`}>
                <img src={photo.thumbnail_url} alt={photo.original_name} />
                <strong>{item.rank}</strong><span>{item.role}</span>
                <i className="moments-tile-hint"><RefreshCw size={14} />点击调整</i>
                {menuOpen && <div className="moments-image-popover" onClick={(event) => event.stopPropagation()}>
                  <b>更换第 {item.rank} 格</b>
                  <button type="button" disabled={smartReplacingRank !== null || availableGroups.length === 0} onClick={() => { setActiveMenuRank(null); setManualReplaceRank(item.rank) }}><RefreshCw size={15} /><span><strong>手动换组</strong><small>选择新分组和具体照片</small></span></button>
                  <button type="button" disabled={smartReplacingRank !== null || availableGroups.length === 0} onClick={() => { void Promise.resolve(onSmartReplace(item.rank)).finally(() => setActiveMenuRank(null)) }}>{replacing ? <LoaderCircle className="spin" size={15} /> : <WandSparkles size={15} />}<span><strong>{replacing ? '正在选择…' : '智能换组'}</strong><small>结合整体和相邻图片选择</small></span></button>
                  <a href={photo.image_url} target="_blank" rel="noreferrer">查看原图</a>
                </div>}
              </div>
            )
          })}
        </div>
        <aside className="moments-insights">
          <div className="moments-adjust-tip"><span><RefreshCw size={17} /></span><div><strong>点击九图中的任意图片</strong><p>可以选择手动换组或智能换组，下载内容会同步更新。</p></div></div>
          <div className="moments-review"><small>整体审美复核</small><p>{selection.grid_review || '已从整体构图、相邻相似度与视觉节奏复核最终九图。'}</p></div>
          <div className="moments-layout"><small>排列思路</small><p>{selection.layout_rationale}</p></div>
        </aside>
      </div>
      <p className="moments-privacy"><LockKeyhole size={12} />仅在点击生成后分析高分分组的代表缩略图，原图不会上传。</p>
      {manualReplaceRank !== null && <div className="dialog-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setManualReplaceRank(null) }}>
        <section className="group-replace-dialog" role="dialog" aria-modal="true" aria-labelledby="group-replace-title">
          <header><div><h2 id="group-replace-title">为第 {manualReplaceRank} 格选择新分组</h2><p>只显示当前九图尚未使用的分组，点击具体照片即可替换</p></div><button type="button" onClick={() => setManualReplaceRank(null)} aria-label="关闭"><X size={18} /></button></header>
          <div className="replace-group-grid">
            {availableGroups.map((group) => {
              const cover = byId.get(group.photo_ids[0])
              return <article key={group.id}><header><strong>{group.name}</strong><span>{group.photo_ids.length} 张 · 最高 {cover?.quality.score ?? 0} 分</span></header><div>{group.photo_ids.map((photoId) => {
                const candidate = byId.get(photoId)
                if (!candidate) return null
                return <button type="button" key={photoId} onClick={() => { onReplace(manualReplaceRank, group.id, photoId, '由你从新的分组中手动选择。', '手动精选'); setManualReplaceRank(null) }} title={`${candidate.original_name} · ${candidate.quality.score} 分`}><img src={candidate.thumbnail_url} alt="" /><span>{candidate.quality.score}</span></button>
              })}</div></article>
            })}
            {availableGroups.length === 0 && <p className="no-replacement-groups">所有分组都已经用于当前九图，没有其他分组可以替换。</p>}
          </div>
        </section>
      </div>}
    </section>
  )
}

function Metric({ label, value }: { label: string; value: number }) {
  return <div><span>{label}</span><i><b style={{ width: `${Math.max(4, value)}%` }} /></i><strong>{Math.round(value)}</strong></div>
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}
