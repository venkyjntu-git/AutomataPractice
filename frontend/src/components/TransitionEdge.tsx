/**
 * TransitionEdge — JFLAP-style automaton transition arrow.
 *
 * Edge path: straight line from circle border to circle border.
 * Self-loop:  cubic bezier arc above the node.
 *
 * Selection:  blue highlighted stroke when selected (like JFLAP).
 * Label drag: drag the label pill to reposition it (like dragging states).
 *             Offset is stored in edge data and committed on mouse-up.
 *
 * Label formats:
 *   DFA / NFA  : symbol            (e.g.  "a" or "ε")
 *   PDA        : sym, top / push   (e.g.  "a, Z / AZ")
 *   TM         : sym / write, dir  (e.g.  "a / b, R")
 */
import { memo, useRef, useState } from 'react'
import { BaseEdge, EdgeLabelRenderer, useEdges, type EdgeProps } from '@xyflow/react'
import { NODE_OUTER } from './StateNode'

export interface TransitionEdgeData {
  machine:       string
  symbol:        string
  stack_top?:    string
  stack_push?:   string
  write?:        string
  direction?:    string
  labelOffsetX?: number   // px offset from default label position
  labelOffsetY?: number
  onDelete:      (id: string) => void
  onEdit:        (id: string) => void
  onOffsetChange:(id: string, x: number, y: number) => void
}

const NODE_RADIUS = NODE_OUTER / 2 - 5   // ≈ 22 px — tip lands at inner circle edge

// ── Label formatting ──────────────────────────────────────────────────────────

export function formatTransitionLabel(d: TransitionEdgeData | null | undefined): string {
  if (!d) return 'ε'
  const sym = d.symbol || 'ε'
  if (d.machine === 'PDA') return `${sym}, ${d.stack_top || 'ε'} / ${d.stack_push || 'ε'}`
  if (d.machine === 'TM')  return `${sym} / ${d.write || 'ε'}, ${d.direction || 'R'}`
  return sym
}

// ── Path helpers ──────────────────────────────────────────────────────────────

/**
 * curved = false → straight line (no reverse edge exists)
 * curved = true  → quadratic bezier bowed in the direction of (-uy, ux).
 *
 * The key insight: for a bidirectional pair the direction vector (ux, uy)
 * is REVERSED on the return edge, so (-uy, ux) automatically points in the
 * OPPOSITE perpendicular direction — no extra sign bookkeeping needed.
 *
 *   q0→q1  ux=+1,uy=0 → (-uy,ux)=(0,+1) → control point BELOW the line ↓
 *   q1→q0  ux=-1,uy=0 → (-uy,ux)=(0,-1) → control point ABOVE the line ↑
 */
function normalPath(
  sx: number, sy: number,
  tx: number, ty: number,
  curved: boolean,
): [string, number, number] {
  const dx   = tx - sx
  const dy   = ty - sy
  const dist = Math.hypot(dx, dy)
  if (dist < 1) return [`M ${sx} ${sy} L ${tx} ${ty}`, sx, sy - 20]

  const ux = dx / dist
  const uy = dy / dist

  const fromX = sx + NODE_RADIUS * ux
  const fromY = sy + NODE_RADIUS * uy
  const toX   = tx - NODE_RADIUS * ux
  const toY   = ty - NODE_RADIUS * uy

  const midX = (fromX + toX) / 2
  const midY = (fromY + toY) / 2

  // Perpendicular direction: (-uy, ux) — 90° CCW in screen coords.
  // Reverses automatically for the reverse edge, separating the two arcs.
  const perpX = -uy
  const perpY =  ux

  if (curved) {
    const CURVE = 40
    const cpX = midX + perpX * CURVE
    const cpY = midY + perpY * CURVE

    const path = `M ${fromX} ${fromY} Q ${cpX} ${cpY} ${toX} ${toY}`

    // Label near the arc apex (75% of the way to the control point)
    const labelX = midX + perpX * CURVE * 0.75
    const labelY = midY + perpY * CURVE * 0.75

    return [path, labelX, labelY]
  }

  // Straight line — label 14 px in the perpendicular direction
  const labelX = midX + perpX * 14
  const labelY = midY + perpY * 14

  return [`M ${fromX} ${fromY} L ${toX} ${toY}`, labelX, labelY]
}

/**
 * index = 0,1,2,… for the first, second, third self-loop on the same node.
 * Each subsequent loop rises higher so they stack upward without overlapping.
 */
function selfLoopPath(cx: number, cy: number, index: number): [string, number, number] {
  const r      = NODE_OUTER / 2
  const rise   = 65 + index * 45   // stack: 65, 110, 155, …
  const spread = 50

  const sx = cx + r * 0.65;  const sy = cy - r * 0.65
  const tx = cx - r * 0.65;  const ty = cy - r * 0.65

  const path   = `M ${sx} ${sy} C ${sx+spread} ${sy-rise} ${tx-spread} ${ty-rise} ${tx} ${ty}`
  const labelX = cx
  const labelY = cy - r - rise * 0.65

  return [path, labelX, labelY]
}

// ── Component ─────────────────────────────────────────────────────────────────

function TransitionEdge({
  id, source, target,
  sourceX, sourceY, targetX, targetY,
  data, selected,
}: EdgeProps) {
  const d = data as unknown as TransitionEdgeData

  // Correct Position.Top offset: ReactFlow gives (center_x, node_top) — add half height
  const HALF = NODE_OUTER / 2
  const sx = sourceX,  sy = sourceY + HALF
  const tx = targetX,  ty = targetY + HALF

  const edges = useEdges()

  // Detect if a reverse edge exists so we can bow both arcs apart
  const hasReverse = edges.some(
    (e) => e.id !== id && e.source === target && e.target === source
  )

  const isSelfLoop = source === target

  // For self-loops: determine stacking index (0 = lowest arc, 1 = next, …)
  // Sort by edge id (creation order) for a stable, consistent ordering.
  const selfLoopIndex = isSelfLoop
    ? edges
        .filter((e) => e.source === source && e.target === source)
        .sort((a, b) => a.id.localeCompare(b.id))
        .findIndex((e) => e.id === id)
    : 0

  const [edgePath, baseLabelX, baseLabelY] = isSelfLoop
    ? selfLoopPath(sx, sy, selfLoopIndex)
    : normalPath(sx, sy, tx, ty, hasReverse)

  const label = formatTransitionLabel(d)

  // ── Label drag ──────────────────────────────────────────────────────────
  // Committed offset lives in edge data; live delta is local state during drag.
  const committedX = d?.labelOffsetX ?? 0
  const committedY = d?.labelOffsetY ?? 0
  const [dragDelta, setDragDelta] = useState<{ x: number; y: number } | null>(null)

  const dragStart = useRef<{ mx: number; my: number } | null>(null)

  const labelX = baseLabelX + committedX + (dragDelta?.x ?? 0)
  const labelY = baseLabelY + committedY + (dragDelta?.y ?? 0)

  function handleLabelMouseDown(e: React.MouseEvent) {
    e.preventDefault()
    e.stopPropagation()
    dragStart.current = { mx: e.clientX, my: e.clientY }
    setDragDelta({ x: 0, y: 0 })

    function onMove(me: MouseEvent) {
      if (!dragStart.current) return
      setDragDelta({ x: me.clientX - dragStart.current.mx, y: me.clientY - dragStart.current.my })
    }

    function onUp(me: MouseEvent) {
      if (dragStart.current) {
        const finalX = committedX + (me.clientX - dragStart.current.mx)
        const finalY = committedY + (me.clientY - dragStart.current.my)
        d?.onOffsetChange(id, finalX, finalY)
      }
      dragStart.current = null
      setDragDelta(null)
      document.removeEventListener('mousemove', onMove)
      document.removeEventListener('mouseup', onUp)
    }

    document.addEventListener('mousemove', onMove)
    document.addEventListener('mouseup', onUp)
  }

  const strokeColor = selected ? '#3b82f6' : '#374151'
  const strokeWidth = selected ? 2 : 1.5

  return (
    <>
      <BaseEdge
        id={id}
        path={edgePath}
        markerEnd={selected ? 'url(#arrowhead-selected)' : 'url(#arrowhead)'}
        style={{ stroke: strokeColor, strokeWidth }}
      />

      <EdgeLabelRenderer>
        <div
          style={{
            position:  'absolute',
            transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`,
            pointerEvents: 'all',
            cursor: dragDelta ? 'grabbing' : 'grab',
          }}
          className="nodrag nopan"
          onMouseDown={handleLabelMouseDown}
        >
          <div className="group relative">
            <span
              className={[
                'bg-white rounded px-1.5 py-0.5 text-xs font-mono shadow-sm select-none whitespace-nowrap border',
                selected ? 'border-blue-400 text-blue-700' : 'border-slate-300 text-slate-700',
              ].join(' ')}
              onDoubleClick={(e) => { e.stopPropagation(); d?.onEdit(id) }}
            >
              {label}
            </span>
            {/* Delete button — visible on hover */}
            <button
              className="absolute -top-2 -right-2 hidden group-hover:flex
                         w-4 h-4 rounded-full bg-red-500 text-white text-[10px]
                         items-center justify-center leading-none shadow"
              title="Delete transition"
              onMouseDown={(e) => e.stopPropagation()}
              onClick={(e) => { e.stopPropagation(); d?.onDelete(id) }}
            >
              ×
            </button>
          </div>
        </div>
      </EdgeLabelRenderer>
    </>
  )
}

export default memo(TransitionEdge)
