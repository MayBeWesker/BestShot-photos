import { useEffect, useRef, useState } from 'react'
import { BookOpen, Check, Copy, LoaderCircle } from 'lucide-react'
import { createPoetryRecommendations } from '../api'
import type { PoetryResponse } from '../types'

interface Props {
  projectId: string
  photoIds: string[]
  caption: string
  disabled: boolean
}

export function PoetrySuggestions({ projectId, photoIds, caption, disabled }: Props) {
  const [emotion, setEmotion] = useState('')
  const [result, setResult] = useState<PoetryResponse | null>(null)
  const [active, setActive] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [copied, setCopied] = useState('')
  const alive = useRef(true)
  useEffect(() => { alive.current = true; return () => { alive.current = false } }, [])
  const recommend = async () => {
    if (loading || disabled) return
    setLoading(true)
    setError('')
    setCopied('')
    try {
      const next = await createPoetryRecommendations(projectId, photoIds, caption, emotion.trim())
      if (alive.current) { setResult(next); setActive(0) }
    } catch (reason) {
      if (alive.current) setError(reason instanceof Error ? reason.message : '诗句匹配失败，请重试。')
    } finally {
      if (alive.current) setLoading(false)
    }
  }
  const poem = result?.recommendations[active]
  const copy = async (withCaption: boolean) => {
    if (!poem) return
    const verse = `${poem.verse}\n——${poem.author}《${poem.title}》`
    try {
      await navigator.clipboard.writeText(withCaption ? `${caption}\n\n${verse}` : verse)
      if (alive.current) setCopied(withCaption ? 'caption' : 'verse')
    } catch { setError('复制失败，请选中文字复制。') }
  }
  return <section className="moments-control-card poetry-card" aria-label="诗句推荐">
    <header><BookOpen size={17} /><strong>诗句推荐</strong></header>
    <label className="poetry-emotion"><span>想表达的心情（可选）</span><textarea aria-label="诗句心情" value={emotion} maxLength={300} rows={2} disabled={loading || disabled} placeholder="例如：雨后释然，想慢慢享受当下" onChange={(event) => { setEmotion(event.target.value); setResult(null); setError(''); setCopied('') }} /></label>
    <button className="poetry-match" type="button" disabled={loading || disabled} onClick={() => void recommend()}>{loading ? <LoaderCircle className="spin" size={15} /> : <BookOpen size={15} />}{loading ? '正在匹配…' : result ? '重新匹配' : '匹配诗句'}</button>
    {error && <p className="poetry-error" role="alert">{error}</p>}
    {result && result.recommendations.length === 0 && <p className="poetry-empty">暂未找到贴切的诗句，可以补充心情后重试。</p>}
    {poem && <div className="poetry-result" aria-live="polite">
      {result!.recommendations.length > 1 && <div className="poetry-options" role="group" aria-label="切换诗句">{result!.recommendations.map((item, index) => <button type="button" key={item.id} aria-pressed={active === index} onClick={() => { setActive(index); setCopied('') }}>推荐{index + 1}</button>)}</div>}
      <blockquote>{poem.verse}</blockquote>
      <a className="poetry-source" href={poem.source_url} target="_blank" rel="noreferrer">{poem.era} · {poem.author}《{poem.title}》↗</a>
      <p className="poetry-reason">{poem.reason}</p>
      <small className="poetry-matches">呼应第 {poem.matched_ranks.join('、')} 张</small>
      <div className="poetry-copy"><button type="button" onClick={() => void copy(false)}>{copied === 'verse' ? <Check size={13} /> : <Copy size={13} />}{copied === 'verse' ? '已复制' : '复制诗句'}</button><button type="button" onClick={() => void copy(true)}>{copied === 'caption' ? <Check size={13} /> : <Copy size={13} />}{copied === 'caption' ? '已复制' : '复制配文'}</button></div>
    </div>}
  </section>
}
