import { useMemo, useState } from 'react'
import {
  ArrowLeft, Brush, Check, ChevronLeft, ChevronRight, CircleAlert, Download, Eraser,
  Eye, EyeOff, ImageDown, LoaderCircle, RefreshCw, RotateCcw, RotateCw, SlidersHorizontal,
  Sparkles, Trash2, WandSparkles,
} from 'lucide-react'
import { activateVersion, composeProject, getProject, withCacheBust } from '../api'
import type { BlendMethod, PhotoProject, Stroke, ToolMode } from '../types'
import { ComparisonSlider } from './ComparisonSlider'
import { ImageCanvas } from './ImageCanvas'

interface Props {
  project: PhotoProject
  onProject: (project: PhotoProject) => void
  onReset: () => void
  onError: (message: string) => void
}

function maskBlob(strokes: Stroke[], width: number, height: number): Promise<Blob> {
  const canvas = document.createElement('canvas')
  canvas.width = width
  canvas.height = height
  const context = canvas.getContext('2d')
  if (!context) return Promise.reject(new Error('浏览器无法创建遮罩画布。'))
  context.fillStyle = '#000'
  context.fillRect(0, 0, width, height)
  context.lineCap = 'round'
  context.lineJoin = 'round'
  for (const stroke of strokes) {
    if (stroke.points.length < 2) continue
    context.beginPath()
    context.strokeStyle = stroke.mode === 'eraser' ? '#000' : '#fff'
    context.lineWidth = stroke.width
    context.moveTo(stroke.points[0], stroke.points[1])
    for (let index = 2; index < stroke.points.length; index += 2) {
      context.lineTo(stroke.points[index], stroke.points[index + 1])
    }
    if (stroke.points.length === 2) {
      context.lineTo(stroke.points[0] + 0.01, stroke.points[1] + 0.01)
    }
    context.stroke()
  }
  return new Promise((resolve, reject) => canvas.toBlob((blob) => blob ? resolve(blob) : reject(new Error('遮罩生成失败。')), 'image/png'))
}

export function ImageEditor({ project, onProject, onReset, onError }: Props) {
  const [strokes, setStrokes] = useState<Stroke[]>([])
  const [redoStrokes, setRedoStrokes] = useState<Stroke[]>([])
  const [tool, setTool] = useState<ToolMode>('brush')
  const [brushWidth, setBrushWidth] = useState(80)
  const [blendMethod, setBlendMethod] = useState<BlendMethod>('feather')
  const [featherRadius, setFeatherRadius] = useState(12)
  const [localAlignment, setLocalAlignment] = useState(true)
  const [processing, setProcessing] = useState(false)
  const [showCompare, setShowCompare] = useState(false)
  const [warnings, setWarnings] = useState<string[]>([])

  const current = useMemo(() => project.versions.find((item) => item.version === project.current_version) ?? project.versions[0], [project])
  const parentVersion = current.parent_version
  const redoVersion = useMemo(() => [...project.versions].reverse().find((item) => item.parent_version === project.current_version)?.version, [project])
  const imageUrl = withCacheBust(current.result_url, project.current_version)
  const mainUrl = withCacheBust(project.main_image.url, project.id)

  const addStroke = (stroke: Stroke) => {
    setStrokes((items) => [...items, stroke])
    setRedoStrokes([])
  }

  const undoStroke = () => {
    setStrokes((items) => {
      if (!items.length) return items
      setRedoStrokes((redo) => [...redo, items[items.length - 1]])
      return items.slice(0, -1)
    })
  }

  const redoStroke = () => {
    setRedoStrokes((items) => {
      if (!items.length) return items
      setStrokes((done) => [...done, items[items.length - 1]])
      return items.slice(0, -1)
    })
  }

  const switchVersion = async (version?: number | null) => {
    if (version === undefined || version === null || processing) return
    try {
      setProcessing(true)
      const next = await activateVersion(project.id, version)
      onProject(next)
      setWarnings(next.versions.find((item) => item.version === version)?.warnings ?? [])
    } catch (error) {
      onError(error instanceof Error ? error.message : '切换版本失败。')
    } finally {
      setProcessing(false)
    }
  }

  const apply = async () => {
    if (!strokes.some((stroke) => stroke.mode === 'brush')) {
      onError('请先涂抹需要替换的区域。')
      return
    }
    try {
      setProcessing(true)
      setWarnings([])
      const mask = await maskBlob(strokes, project.main_image.width, project.main_image.height)
      const result = await composeProject(project.id, mask, {
        baseVersion: project.current_version,
        blendMethod,
        featherRadius,
        useLocalAlignment: localAlignment,
      })
      const updated = await getProject(project.id)
      onProject(updated)
      setStrokes([])
      setRedoStrokes([])
      setWarnings(result.warnings)
    } catch (error) {
      onError(error instanceof Error ? error.message : '合成失败。')
    } finally {
      setProcessing(false)
    }
  }

  return (
    <section className="editor-screen">
      <header className="editor-header">
        <button className="brand-button" type="button" onClick={onReset} aria-label="返回上传页面">
          <span className="brand-mark"><Sparkles size={17} /></span><span><strong>BestShot</strong><small>MERGE</small></span>
        </button>
        <div className="workflow-steps" aria-label="处理步骤">
          <div className="done"><span><Check size={12} /></span>上传</div><i />
          <div className="done"><span><Check size={12} /></span>自动对齐</div><i />
          <div className="active"><span>3</span>涂抹替换</div>
        </div>
        <div className="header-actions">
          <button className="quiet-button" type="button" onClick={() => setShowCompare((value) => !value)}>
            {showCompare ? <EyeOff size={17} /> : <Eye size={17} />}{showCompare ? '返回编辑' : '前后对比'}
          </button>
          <a className="export-button" href={`/api/projects/${project.id}/export`} download><Download size={17} />导出高清图</a>
        </div>
      </header>

      <div className="editor-body">
        <aside className="left-panel">
          <div className="panel-section source-section">
            <div className="panel-title"><span>照片来源</span><small>已自动对齐</small></div>
            <div className="source-stack">
              <div className="source-thumb selected"><img src={mainUrl} alt="主照片" /><span>A · 主照片</span><Check size={13} /></div>
              <div className="source-thumb"><img src={withCacheBust(project.source_image.url, project.id)} alt="素材照片" /><span>B · 素材</span></div>
            </div>
          </div>

          <div className="panel-section">
            <div className="panel-title"><span>涂抹工具</span><small>{strokes.length} 笔</small></div>
            <div className="tool-switch">
              <button className={tool === 'brush' ? 'active' : ''} type="button" onClick={() => setTool('brush')}><Brush size={17} />画笔</button>
              <button className={tool === 'eraser' ? 'active' : ''} type="button" onClick={() => setTool('eraser')}><Eraser size={17} />橡皮</button>
            </div>
            <label className="range-control">
              <div><span>画笔大小</span><output>{brushWidth}px</output></div>
              <input type="range" min="12" max="260" value={brushWidth} onChange={(event) => setBrushWidth(Number(event.target.value))} />
              <div className="range-ends"><small>精细</small><small>大范围</small></div>
            </label>
            <div className="stroke-actions">
              <button type="button" disabled={!strokes.length} onClick={undoStroke} title="撤销笔迹"><RotateCcw size={16} /></button>
              <button type="button" disabled={!redoStrokes.length} onClick={redoStroke} title="重做笔迹"><RotateCw size={16} /></button>
              <button type="button" disabled={!strokes.length} onClick={() => { setStrokes([]); setRedoStrokes([]) }}><Trash2 size={15} />清除</button>
            </div>
          </div>

          <div className="panel-section history-section">
            <div className="panel-title"><span>版本历史</span><small>{project.versions.length}/11</small></div>
            <div className="version-nav">
              <button type="button" disabled={parentVersion === null || processing} onClick={() => switchVersion(parentVersion)}><ChevronLeft size={16} />上一步</button>
              <strong>v{project.current_version}</strong>
              <button type="button" disabled={redoVersion === undefined || processing} onClick={() => switchVersion(redoVersion)}>下一步<ChevronRight size={16} /></button>
            </div>
          </div>
        </aside>

        <main className="canvas-workspace">
          <div className="workspace-topline">
            <div><span className="live-dot" />{showCompare ? '前后效果对比' : '在主照片上涂抹要替换的位置'}</div>
            <small>{project.main_image.width} × {project.main_image.height} px</small>
          </div>
          <div className="canvas-shell">
            {showCompare ? (
              <ComparisonSlider beforeUrl={mainUrl} afterUrl={imageUrl} />
            ) : (
              <ImageCanvas
                imageUrl={imageUrl}
                imageWidth={project.main_image.width}
                imageHeight={project.main_image.height}
                strokes={strokes}
                tool={tool}
                brushWidth={brushWidth}
                disabled={processing}
                onStroke={addStroke}
              />
            )}
            {processing && <div className="processing-overlay"><LoaderCircle className="spin" size={28} /><strong>正在生成自然融合效果</strong><span>局部对齐与边缘检查可能需要几秒</span></div>}
          </div>
          {warnings.length > 0 && <div className="warning-banner"><CircleAlert size={17} /><div>{warnings.map((warning) => <p key={warning}>{warning}</p>)}</div></div>}
        </main>

        <aside className="right-panel">
          <div className="settings-heading"><SlidersHorizontal size={18} /><div><strong>融合设置</strong><small>调整替换区域的处理方式</small></div></div>
          <div className="setting-group">
            <label>融合算法</label>
            <div className="blend-options">
              <button className={blendMethod === 'feather' ? 'active' : ''} type="button" onClick={() => setBlendMethod('feather')}>
                <span><WandSparkles size={17} /></span><div><strong>羽化融合</strong><small>保留真实像素，推荐</small></div>{blendMethod === 'feather' && <Check size={15} />}
              </button>
              <button className={blendMethod.startsWith('poisson') ? 'active' : ''} type="button" onClick={() => setBlendMethod('poisson_normal')}>
                <span><ImageDown size={17} /></span><div><strong>Poisson</strong><small>平衡边界光照</small></div>{blendMethod.startsWith('poisson') && <Check size={15} />}
              </button>
            </div>
            {blendMethod.startsWith('poisson') && (
              <select value={blendMethod} onChange={(event) => setBlendMethod(event.target.value as BlendMethod)}>
                <option value="poisson_normal">标准克隆</option><option value="poisson_mixed">混合梯度</option>
              </select>
            )}
          </div>
          {blendMethod === 'feather' && (
            <label className="range-control setting-group">
              <div><span>边缘柔和度</span><output>{featherRadius}px</output></div>
              <input type="range" min="2" max="40" value={featherRadius} onChange={(event) => setFeatherRadius(Number(event.target.value))} />
              <p>边缘明显时可适当增加，头发等细节区域建议减小。</p>
            </label>
          )}
          <div className="setting-group toggle-row">
            <div><strong>局部自动对齐</strong><small>修正人物的轻微位移</small></div>
            <button className={localAlignment ? 'toggle on' : 'toggle'} type="button" aria-pressed={localAlignment} onClick={() => setLocalAlignment((value) => !value)}><span /></button>
          </div>
          <div className="alignment-card">
            <div><span className="success-icon"><Check size={14} /></span><div><strong>全局配准良好</strong><small>{project.alignment?.inlier_count ?? 0} 个有效特征点</small></div></div>
            <dl><div><dt>内点率</dt><dd>{Math.round((project.alignment?.inlier_ratio ?? 0) * 100)}%</dd></div><div><dt>中位误差</dt><dd>{project.alignment?.reprojection_error?.toFixed(1) ?? '—'} px</dd></div></dl>
          </div>
          <button className="apply-button" type="button" disabled={processing || !strokes.length || showCompare} onClick={apply}>
            {processing ? <LoaderCircle className="spin" size={19} /> : <Sparkles size={19} />}应用替换
          </button>
          <p className="apply-note">每次应用都会创建一个可撤销的新版本</p>
        </aside>
      </div>
    </section>
  )
}

