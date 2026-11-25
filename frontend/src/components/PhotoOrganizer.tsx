import { useEffect, useMemo, useRef, useState } from 'react'
import { ArrowLeft, Bot, Check, ChevronRight, Copy, Download, Images, Layers3, LoaderCircle, LockKeyhole, Medal, Plus, RefreshCw, Sparkles, Trash2, UploadCloud, WandSparkles, X } from 'lucide-react'
import { createMomentsRegeneration, createMomentsReplacement, createMomentsSelection, createOrganizerProject, deleteOrganizerProject, downloadMomentsArchive } from '../api'
import type { GroupSensitivity, MomentsContext, MomentsSelection, MomentsTone, OrganizerProject, PhotoGroup } from '../types'

interface Props {
  onError: (message: string) => void
  onActiveChange: (active: boolean) => void
  onMerge: (projectId: string, mainPhotoId: string, sourcePhotoId: string) => Promise<void>
}

const modes: { value: GroupSensitivity; label: string; description: string }[] = [
  { value: 'conservative', label: '保守', description: '宁可多分组，减少误合并' },
  { value: 'standard', label: '标准', description: '适合大多数旅行相册' },
  { value: 'loose', label: '宽松', description: '合并更多相近构图' },
]

export function PhotoOrganizer({ onError, onActiveChange, onMerge }: Props) {
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
    return <OrganizerResults project={project} selected={selected} onSelect={setSelectedGroupId} onReset={reset} onError={onError} onMerge={onMerge} />
  }

  return (
    <main className="organizer-upload">
      <section className="organizer-intro">
        <div className="eyebrow"><span /> SMART PHOTO ORGANIZER</div>
        <h1><span>只管记录精彩，</span><span>剩下的交给 <em>BestShot</em></span></h1>
        <p>一次导入整趟旅程，自动归组、挑出好照片，再整理成值得分享的故事。</p>
        <div className="organizer-feature-list">
          <div><Check size={15} /><strong>自动归组</strong></div>
          <div><Medal size={15} /><strong>质量排序</strong></div>
          <div><LockKeyhole size={15} /><strong>本地处理</strong></div>
        </div>
      </section>

      <section className="batch-card">
        <div className="batch-card-heading">
          <div><h2>导入照片</h2><p>一次选择整个旅程</p></div>
          <span>{files.length} / 200</span>
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
            <div className="dropzone-empty"><UploadCloud size={30} /><strong>拖放或选择照片</strong><span>JPG · PNG · WebP · HEIC / HEIF</span></div>
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
          {loading ? <><LoaderCircle className="spin" size={17} />正在分析 {files.length} 张照片…</> : <><Sparkles size={16} />开始整理<ChevronRight size={16} /></>}
        </button>
        <p className="upload-tip">本地分析 · 原图不会离开你的设备</p>
      </section>
    </main>
  )
}

function OrganizerResults({ project, selected, onSelect, onReset, onError, onMerge }: { project: OrganizerProject; selected?: PhotoGroup; onSelect: (id: string) => void; onReset: () => void; onError: (message: string) => void; onMerge: Props['onMerge'] }) {
  const [moments, setMoments] = useState<MomentsSelection | null>(null)
  const [selectingMoments, setSelectingMoments] = useState(false)
  const [regeneratingMoments, setRegeneratingMoments] = useState(false)
  const [downloadingMoments, setDownloadingMoments] = useState(false)
  const [smartReplacingRank, setSmartReplacingRank] = useState<number | null>(null)
  const [contextDialogOpen, setContextDialogOpen] = useState(false)
  const [regenerationDialogOpen, setRegenerationDialogOpen] = useState(false)
  const [mergeMainId, setMergeMainId] = useState<string | null>(null)
  const [merging, setMerging] = useState(false)
  const groupButtonRefs = useRef(new Map<string, HTMLButtonElement>())
  const byId = new Map(project.photos.map((photo) => [photo.id, photo]))
  const selectedPhotos = (selected?.photo_ids ?? []).map((id) => byId.get(id)).filter(Boolean) as OrganizerProject['photos']
  const mergeGroup = project.groups.find((group) => mergeMainId && group.photo_ids.includes(mergeMainId))

  const startGroupMerge = async (sourceId: string) => {
    if (!mergeMainId || merging) return
    try {
      setMerging(true)
      await onMerge(project.id, mergeMainId, sourceId)
      setMergeMainId(null)
    } catch (reason) {
      onError(reason instanceof Error ? reason.message : '无法合成这些照片。')
    } finally { setMerging(false) }
  }

  useEffect(() => {
    if (!selected?.id) return
    groupButtonRefs.current.get(selected.id)?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  }, [selected?.id])

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

  const regenerateMoments = async (instruction: string) => {
    if (!moments) return
    try {
      setRegeneratingMoments(true)
      const result = await createMomentsRegeneration(project.id, moments, instruction.slice(0, 800))
      setMoments(result)
      setRegenerationDialogOpen(false)
      if (result.selected[0]?.group_id) onSelect(result.selected[0].group_id)
    } catch (reason) {
      onError(reason instanceof Error ? reason.message : '九图重新生成失败。')
    } finally {
      setRegeneratingMoments(false)
    }
  }

  const smartReplaceMoment = async (rank: number) => {
    if (!moments) return
    try {
      setSmartReplacingRank(rank)
      const replacement = await createMomentsReplacement(project.id, moments.selected.map((item) => item.photo_id), rank)
      replaceMomentGroup(rank, replacement.group_id, replacement.photo_id, replacement.reason, replacement.role, replacement.grid_review)
      onSelect(replacement.group_id)
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
                <button ref={(node) => { if (node) groupButtonRefs.current.set(group.id, node); else groupButtonRefs.current.delete(group.id) }} key={group.id} className={selected?.id === group.id ? 'active' : ''} type="button" onClick={() => onSelect(group.id)}>
                  {cover && <img src={cover.thumbnail_url} alt="" />}
                  <span><strong>{group.name}</strong><small>{group.photo_ids.length} 张 · 最高 {cover?.quality.score ?? 0} 分</small></span>
                  <ChevronRight size={14} />
                </button>
              )
            })}
          </div>
        </aside>
        <section className="photo-group-view">
          {moments && <MomentsResult selection={moments} project={project} downloading={downloadingMoments} regenerating={regeneratingMoments} smartReplacingRank={smartReplacingRank} onDownload={downloadMoments} onReplace={replaceMomentGroup} onSmartReplace={smartReplaceMoment} onRegenerate={() => setRegenerationDialogOpen(true)} onSelectGroup={onSelect} />}
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
                  <button className="group-merge-action" type="button" disabled={selectedPhotos.length < 2} onClick={() => setMergeMainId(photo.id)} title={selectedPhotos.length < 2 ? '本组需要至少两张照片才能合成' : '以这张为主图，选择同组照片补充细节'}><Layers3 size={15} />照片合成</button>
                </div>
              </article>
            ))}
          </div>
        </section>
      </div>
      {contextDialogOpen && <MomentsContextDialog loading={selectingMoments} onClose={() => setContextDialogOpen(false)} onGenerate={selectForMoments} />}
      {moments && regenerationDialogOpen && <MomentsRegenerationDialog loading={regeneratingMoments} onClose={() => setRegenerationDialogOpen(false)} onGenerate={regenerateMoments} />}
      {mergeMainId && mergeGroup && <div className="dialog-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget && !merging) setMergeMainId(null) }}>
        <section className="group-replace-dialog" role="dialog" aria-modal="true" aria-labelledby="group-merge-title">
          <header><div><h2 id="group-merge-title">选择一张照片补充细节</h2><p>以当前照片为主图，进入合成编辑器后涂抹需要替换的区域。</p></div><button type="button" disabled={merging} onClick={() => setMergeMainId(null)} aria-label="关闭"><X size={18} /></button></header>
          <div className="group-merge-candidates">{mergeGroup.photo_ids.filter((id) => id !== mergeMainId).map((id) => {
            const photo = byId.get(id)
            return photo && <button type="button" key={id} disabled={merging} onClick={() => void startGroupMerge(id)}><img src={photo.thumbnail_url} alt={photo.original_name} /><span>{photo.quality.score} 分</span></button>
          })}</div>
          {merging && <p className="group-merge-status" role="status"><LoaderCircle className="spin" size={16} />正在对齐照片…</p>}
        </section>
      </div>}
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

function MomentsRegenerationDialog({ loading, onClose, onGenerate }: { loading: boolean; onClose: () => void; onGenerate: (instruction: string) => void }) {
  const [instruction, setInstruction] = useState('')
  return (
    <div className="dialog-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget && !loading) onClose() }}>
      <form className="moments-dialog moments-regeneration-dialog" role="dialog" aria-modal="true" aria-labelledby="moments-regeneration-title" onSubmit={(event) => { event.preventDefault(); onGenerate(instruction.trim()) }}>
        <header><div><span><RefreshCw size={18} /></span><div><h2 id="moments-regeneration-title">重新生成九图</h2></div></div><button type="button" disabled={loading} onClick={onClose} aria-label="关闭"><X size={17} /></button></header>
        <label className="regeneration-field"><span>修改要求（可选）</span><textarea value={instruction} maxLength={800} rows={5} onChange={(event) => setInstruction(event.target.value)} placeholder="例如：减少夜景，多选人物和旅行细节，整体更轻松。" /><small>{instruction.length} / 800</small></label>
        <p className="dialog-data-note"><LockKeyhole size={13} />仅携带当前结果的精简快照，不累积完整对话历史</p>
        <footer><button type="button" className="dialog-skip" disabled={loading} onClick={onClose}>取消</button><button type="submit" className="dialog-generate" disabled={loading}>{loading ? <LoaderCircle className="spin" size={15} /> : <RefreshCw size={15} />}{loading ? '正在重新生成…' : '重新生成'}</button></footer>
      </form>
    </div>
  )
}

function MomentsResult({ selection, project, downloading, regenerating, smartReplacingRank, onDownload, onReplace, onSmartReplace, onRegenerate, onSelectGroup }: { selection: MomentsSelection; project: OrganizerProject; downloading: boolean; regenerating: boolean; smartReplacingRank: number | null; onDownload: () => void; onReplace: (rank: number, groupId: string, photoId: string, reason: string, role?: string, gridReview?: string) => void; onSmartReplace: (rank: number) => Promise<void>; onRegenerate: () => void; onSelectGroup: (groupId: string) => void }) {
  const [manualReplaceRank, setManualReplaceRank] = useState<number | null>(null)
  const [activeMenuRank, setActiveMenuRank] = useState<number | null>(null)
  const [activePreviewRank, setActivePreviewRank] = useState(selection.selected[0]?.rank ?? 1)
  const [captionCopied, setCaptionCopied] = useState(false)
  const byId = new Map(project.photos.map((photo) => [photo.id, photo]))
  const groupsById = new Map(project.groups.map((group) => [group.id, group]))
  const usedGroupIds = new Set(selection.selected.map((item) => item.group_id))
  const availableGroups = project.groups.filter((group) => !usedGroupIds.has(group.id))
  const activePreview = selection.selected.find((item) => item.rank === activePreviewRank) ?? selection.selected[0]
  const activePreviewGroup = activePreview ? groupsById.get(activePreview.group_id) : undefined
  const activePreviewPhotos = (activePreviewGroup?.photo_ids ?? []).map((photoId) => byId.get(photoId)).filter(Boolean) as OrganizerProject['photos']

  useEffect(() => {
    if (!selection.selected.some((item) => item.rank === activePreviewRank)) setActivePreviewRank(selection.selected[0]?.rank ?? 1)
  }, [activePreviewRank, selection])
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
      <div className="moments-main-layout">
        <div className="moments-grid">
          {selection.selected.map((item) => {
            const photo = byId.get(item.photo_id)
            if (!photo) return null
            const replacing = smartReplacingRank === item.rank
            const menuOpen = activeMenuRank === item.rank
            return (
              <div className={`moments-tile ${menuOpen ? 'menu-open' : ''} ${activePreview?.rank === item.rank ? 'preview-active' : ''}`} key={item.rank} onClick={() => { setActivePreviewRank(item.rank); onSelectGroup(item.group_id); setActiveMenuRank(null) }} onKeyDown={(event) => { if (event.key === 'Escape') setActiveMenuRank(null) }}>
                <button type="button" className="moments-tile-select" aria-label={`选择第 ${item.rank} 格：${photo.original_name}`} onClick={() => { setActivePreviewRank(item.rank); onSelectGroup(item.group_id); setActiveMenuRank(null) }} />
                <img src={photo.thumbnail_url} alt={photo.original_name} />
                <strong>{item.rank}</strong><span>{item.role}</span>
                <button type="button" className="moments-tile-hint" aria-label={`调整第 ${item.rank} 格`} aria-expanded={menuOpen} onClick={(event) => { event.stopPropagation(); setActivePreviewRank(item.rank); onSelectGroup(item.group_id); setActiveMenuRank(menuOpen ? null : item.rank) }}><RefreshCw size={14} />点击调整</button>
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
          <section className="moments-control-card moments-regenerate-card">
            <div><span><RefreshCw size={17} /></span><strong>重新生成九图</strong></div>
            <button type="button" disabled={regenerating} onClick={onRegenerate}>{regenerating ? <LoaderCircle className="spin" size={15} /> : <WandSparkles size={15} />}{regenerating ? '正在生成…' : '重新生成'}</button>
          </section>
          {activePreview && activePreviewGroup && <section className="moments-control-card moments-group-preview">
            <header><div><small>第 {activePreview.rank} 格 · 当前分组</small><strong>{activePreviewGroup.name}</strong></div><span>{activePreviewPhotos.length} 张</span></header>
            <div className="moments-group-thumbs">
              {activePreviewPhotos.map((photo) => <button type="button" className={photo.id === activePreview.photo_id ? 'active' : ''} key={photo.id} disabled={photo.id === activePreview.photo_id} onClick={() => onReplace(activePreview.rank, activePreview.group_id, photo.id, '由你从当前分组中选择。', activePreview.role)} title={`${photo.original_name} · ${photo.quality.score} 分`}><img src={photo.thumbnail_url} alt={photo.original_name} /><span>{photo.quality.score}</span></button>)}
            </div>
          </section>}
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
                return <button type="button" key={photoId} onClick={() => { onReplace(manualReplaceRank, group.id, photoId, '由你从新的分组中手动选择。', '手动精选'); onSelectGroup(group.id); setManualReplaceRank(null) }} title={`${candidate.original_name} · ${candidate.quality.score} 分`}><img src={candidate.thumbnail_url} alt="" /><span>{candidate.quality.score}</span></button>
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
