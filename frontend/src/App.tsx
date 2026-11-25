import { useState } from 'react'
import { CircleAlert, Images, Layers3, Sparkles, X } from 'lucide-react'
import { alignProject, createProject, deleteProject } from './api'
import { ImageEditor } from './components/ImageEditor'
import { ImageUploader } from './components/ImageUploader'
import { PhotoOrganizer } from './components/PhotoOrganizer'
import type { PhotoProject } from './types'

export default function App() {
  const [mode, setMode] = useState<'organize' | 'merge'>('organize')
  const [organizerActive, setOrganizerActive] = useState(false)
  const [project, setProject] = useState<PhotoProject | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const start = async (main: File, source: File) => {
    try {
      setLoading(true)
      setError(null)
      const created = await createProject(main, source)
      const aligned = await alignProject(created.id)
      setProject(aligned)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '创建项目失败。')
    } finally {
      setLoading(false)
    }
  }

  const reset = async () => {
    const current = project
    setProject(null)
    setError(null)
    if (current) {
      try { await deleteProject(current.id) } catch { /* Local cleanup can be retried on next launch. */ }
    }
  }

  return (
    <div className="app">
      {!project && !organizerActive && (
        <nav className="landing-nav">
          <div className="brand"><span className="brand-mark"><Sparkles size={17} /></span><span><strong>BestShot</strong><small>SMART PHOTO CURATOR</small></span></div>
          <div className="mode-switch">
            <button type="button" className={mode === 'organize' ? 'active' : ''} onClick={() => setMode('organize')}><Images size={14} />智能整理</button>
            <button type="button" className={mode === 'merge' ? 'active' : ''} onClick={() => setMode('merge')}><Layers3 size={14} />照片合成</button>
          </div>
          <span className="local-badge"><i />本地处理</span>
        </nav>
      )}
      {project ? <ImageEditor project={project} onProject={setProject} onReset={reset} onError={setError} /> : mode === 'organize' ? <PhotoOrganizer onError={(message) => setError(message)} onActiveChange={setOrganizerActive} /> : <ImageUploader loading={loading} onSubmit={start} />}
      {error && <div className="error-toast" role="alert"><CircleAlert size={19} /><span>{error}</span><button type="button" onClick={() => setError(null)}><X size={16} /></button></div>}
    </div>
  )
}

