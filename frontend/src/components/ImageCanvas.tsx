import { useEffect, useRef, useState } from 'react'
import { Layer, Line, Stage } from 'react-konva'
import type Konva from 'konva'
import type { Stroke, ToolMode } from '../types'

interface Props {
  imageUrl: string
  imageWidth: number
  imageHeight: number
  strokes: Stroke[]
  tool: ToolMode
  brushWidth: number
  disabled?: boolean
  onStroke: (stroke: Stroke) => void
}

export function ImageCanvas({ imageUrl, imageWidth, imageHeight, strokes, tool, brushWidth, disabled, onStroke }: Props) {
  const wrapperRef = useRef<HTMLDivElement>(null)
  const drawingRef = useRef(false)
  const activeRef = useRef<Stroke | null>(null)
  const [active, setActive] = useState<Stroke | null>(null)
  const [size, setSize] = useState({ width: 800, height: 600 })

  useEffect(() => {
    const element = wrapperRef.current
    if (!element) return
    const update = () => {
      const width = element.clientWidth
      setSize({ width, height: width * imageHeight / imageWidth })
    }
    update()
    const observer = new ResizeObserver(update)
    observer.observe(element)
    return () => observer.disconnect()
  }, [imageWidth, imageHeight])

  const originalPoint = (stage: Konva.Stage | null) => {
    if (!stage) return null
    const pointer = stage.getPointerPosition()
    if (!pointer) return null
    return [pointer.x * imageWidth / size.width, pointer.y * imageHeight / size.height]
  }

  const begin = (event: Konva.KonvaEventObject<PointerEvent>) => {
    if (disabled) return
    const point = originalPoint(event.target.getStage())
    if (!point) return
    const stroke: Stroke = { id: crypto.randomUUID(), mode: tool, points: point, width: brushWidth }
    drawingRef.current = true
    activeRef.current = stroke
    setActive(stroke)
  }

  const move = (event: Konva.KonvaEventObject<PointerEvent>) => {
    if (!drawingRef.current || !activeRef.current) return
    const point = originalPoint(event.target.getStage())
    if (!point) return
    const next = { ...activeRef.current, points: [...activeRef.current.points, ...point] }
    activeRef.current = next
    setActive(next)
  }

  const end = () => {
    if (!drawingRef.current || !activeRef.current) return
    drawingRef.current = false
    const completed = activeRef.current
    activeRef.current = null
    setActive(null)
    onStroke(completed)
  }

  const scaleX = size.width / imageWidth
  const scaleY = size.height / imageHeight
  const renderStroke = (stroke: Stroke) => (
    <Line
      key={stroke.id}
      points={stroke.points.flatMap((value, index) => [value * (index % 2 === 0 ? scaleX : scaleY)])}
      stroke="rgba(235, 92, 67, .55)"
      strokeWidth={stroke.width * scaleX}
      lineCap="round"
      lineJoin="round"
      tension={0.08}
      globalCompositeOperation={stroke.mode === 'eraser' ? 'destination-out' : 'source-over'}
    />
  )

  return (
    <div ref={wrapperRef} className={`image-canvas ${disabled ? 'is-disabled' : ''}`} style={{ aspectRatio: `${imageWidth} / ${imageHeight}` }}>
      <img src={imageUrl} alt="当前编辑照片" draggable={false} />
      <Stage
        width={size.width}
        height={size.height}
        onPointerDown={begin}
        onPointerMove={move}
        onPointerUp={end}
        onPointerLeave={end}
      >
        <Layer>{strokes.map(renderStroke)}{active && renderStroke(active)}</Layer>
      </Stage>
      {strokes.length === 0 && <div className="canvas-hint"><span />按住鼠标，涂抹需要替换的区域</div>}
    </div>
  )
}

