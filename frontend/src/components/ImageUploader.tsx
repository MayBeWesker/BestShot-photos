import { useMemo, useRef, useState } from 'react'
import { ArrowRight, ImagePlus, LockKeyhole, Upload, X } from 'lucide-react'

interface Props {
  loading: boolean
  onSubmit: (main: File, source: File) => void
}

interface PickerProps {
  label: string
  hint: string
  file: File | null
  onFile: (file: File | null) => void
  index: string
}

function PhotoPicker({ label, hint, file, onFile, index }: PickerProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)
  const preview = useMemo(() => (file ? URL.createObjectURL(file) : null), [file])
  const isHeic = Boolean(file && /\.(heic|heif)$/i.test(file.name))

  const accept = (candidate?: File) => {
    if (candidate && (/image\/(jpeg|png|webp|heic|heif)/i.test(candidate.type) || /\.(jpe?g|png|webp|heic|heif)$/i.test(candidate.name))) onFile(candidate)
  }

  return (
    <div
      className={`photo-picker ${dragging ? 'is-dragging' : ''} ${file ? 'has-file' : ''}`}
      onDragOver={(event) => { event.preventDefault(); setDragging(true) }}
      onDragLeave={() => setDragging(false)}
      onDrop={(event) => {
        event.preventDefault()
        setDragging(false)
        accept(event.dataTransfer.files[0])
      }}
    >
      <div className="picker-label"><span>{index}</span><div><strong>{label}</strong><small>{hint}</small></div></div>
      <button className="picker-surface" type="button" onClick={() => inputRef.current?.click()}>
        {preview && !isHeic ? (
          <img src={preview} alt={`${label}预览`} />
        ) : isHeic ? (
          <div className="picker-empty heic-selected"><ImagePlus size={28} /><span>HEIC 照片已选择</span><small>{file?.name}</small></div>
        ) : (
          <div className="picker-empty"><ImagePlus size={28} /><span>点击选择或拖入照片</span><small>JPG / JPEG / PNG / WebP / HEIC</small></div>
        )}
      </button>
      {file && (
        <div className="picker-file">
          <span title={file.name}>{file.name}</span>
          <button type="button" aria-label={`移除${label}`} onClick={() => onFile(null)}><X size={15} /></button>
        </div>
      )}
      <input ref={inputRef} hidden type="file" accept="image/jpeg,image/png,image/webp,image/heic,image/heif,.jpg,.jpeg,.png,.webp,.heic,.heif" onChange={(event) => accept(event.target.files?.[0])} />
    </div>
  )
}

export function ImageUploader({ loading, onSubmit }: Props) {
  const [main, setMain] = useState<File | null>(null)
  const [source, setSource] = useState<File | null>(null)

  return (
    <section className="upload-screen">
      <div className="hero-copy">
        <div className="eyebrow"><span /> 本地运行 · 照片不离开电脑</div>
        <h1>让合照里的<br /><em>每个人</em>都刚刚好。</h1>
        <p>上传同一场景的两张照片，涂抹需要替换的区域。BestShot 会自动对齐、自然融合，并保留原始分辨率。</p>
        <div className="privacy-note"><LockKeyhole size={16} /><span>没有云端上传、账户或第三方模型调用</span></div>
      </div>
      <div className="upload-card">
        <div className="upload-card-head">
          <div><span className="step-kicker">01 / 03</span><h2>选择两张照片</h2></div>
          <Upload size={21} />
        </div>
        <div className="pickers">
          <PhotoPicker label="主照片" hint="作为最终画面的基础" file={main} onFile={setMain} index="A" />
          <div className="merge-mark"><ArrowRight size={18} /></div>
          <PhotoPicker label="素材照片" hint="提供更好的表情或动作" file={source} onFile={setSource} index="B" />
        </div>
        <button className="primary-action" type="button" disabled={!main || !source || loading} onClick={() => main && source && onSubmit(main, source)}>
          {loading ? <><span className="spinner" /> 正在分析并对齐…</> : <>开始自动对齐 <ArrowRight size={18} /></>}
        </button>
        <p className="upload-tip">建议使用同一机位连续拍摄、背景和人物位置接近的照片</p>
      </div>
    </section>
  )
}

