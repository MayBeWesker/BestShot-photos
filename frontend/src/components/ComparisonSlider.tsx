import { useState } from 'react'

interface Props {
  beforeUrl: string
  afterUrl: string
}

export function ComparisonSlider({ beforeUrl, afterUrl }: Props) {
  const [position, setPosition] = useState(50)
  return (
    <div className="comparison-slider">
      <img src={afterUrl} alt="处理后" />
      <div className="comparison-before" style={{ width: `${position}%` }}><img src={beforeUrl} alt="处理前" /></div>
      <div className="comparison-line" style={{ left: `${position}%` }}><span>↔</span></div>
      <span className="compare-label before">之前</span><span className="compare-label after">之后</span>
      <input aria-label="拖动查看前后对比" type="range" min="0" max="100" value={position} onChange={(event) => setPosition(Number(event.target.value))} />
    </div>
  )
}

