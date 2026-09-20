/**
 * StateNode — JFLAP-style circular automaton state.
 *
 * Handles are completely invisible, centered, and cover the full circle.
 * ReactFlow sees the center of the node as the connection point — the
 * TransitionEdge then computes the actual arc endpoint on the circle border.
 *
 * data.connectMode  true  →  handles accept pointer events (TRANSITION tool)
 *                   false →  handles are pointer-events:none (other tools)
 */
import { memo } from 'react'
import { Handle, Position, type NodeProps } from '@xyflow/react'

export const NODE_OUTER = 54   // outer ring diameter (accept state)
export const NODE_INNER = 40   // main circle diameter

export default memo(function StateNode({ data, selected }: NodeProps) {
  const d           = data as Record<string, unknown>
  const accept      = Boolean(d.accept)
  const initial     = Boolean(d.initial)
  const label       = String(d.label ?? '')
  const connectMode = Boolean(d.connectMode)
  const simActive   = Boolean(d.simActive)

  // Handles are invisible but cover the full node circle.
  // pointerEvents depends on mode so they don't swallow clicks when not connecting.
  const handleStyle: React.CSSProperties = {
    position:     'absolute',
    top:          '50%',
    left:         '50%',
    transform:    'translate(-50%, -50%)',
    width:        NODE_OUTER,
    height:       NODE_OUTER,
    borderRadius: '50%',
    background:   'transparent',
    border:       'none',
    opacity:      0,
    pointerEvents: connectMode ? 'all' : 'none',
  }

  return (
    <div style={{
      width:          NODE_OUTER,
      height:         NODE_OUTER,
      position:       'relative',
      display:        'flex',
      alignItems:     'center',
      justifyContent: 'center',
    }}>

      {/* ── Initial-state arrow from the left ── */}
      {initial && (
        <div style={{
          position:   'absolute',
          right:      '100%',
          top:        '50%',
          transform:  'translateY(-50%)',
          display:    'flex',
          alignItems: 'center',
          marginRight: 2,
        }}>
          <div style={{ width: 26, height: 2, background: '#1e293b' }} />
          <div style={{
            width: 0, height: 0,
            borderTop:    '5px solid transparent',
            borderBottom: '5px solid transparent',
            borderLeft:   '8px solid #1e293b',
          }} />
        </div>
      )}

      {/* ── Simulation highlight (amber) ── */}
      {simActive && (
        <div
          style={{
            position:     'absolute',
            width:        NODE_OUTER + 10,
            height:       NODE_OUTER + 10,
            borderRadius: '50%',
            border:       '3px solid #f59e0b',
            boxShadow:    '0 0 0 2px rgba(245, 158, 11, 0.35)',
            pointerEvents: 'none',
            zIndex:       2,
          }}
        />
      )}

      {/* ── Accept-state outer ring ── */}
      {accept && (
        <div style={{
          position:    'absolute',
          width:       NODE_OUTER,
          height:      NODE_OUTER,
          borderRadius: '50%',
          border:       `2px solid ${selected ? '#3b82f6' : '#1e293b'}`,
          boxShadow:    selected ? '0 0 0 2px #93c5fd' : undefined,
        }} />
      )}

      {/* ── Main circle ── */}
      <div style={{
        width:          NODE_INNER,
        height:         NODE_INNER,
        borderRadius:   '50%',
        border:         `2px solid ${selected ? '#3b82f6' : '#1e293b'}`,
        background:     'white',
        display:        'flex',
        alignItems:     'center',
        justifyContent: 'center',
        boxShadow:      selected
          ? '0 0 0 2px #93c5fd'
          : '0 1px 3px rgba(0,0,0,0.10)',
        userSelect: 'none',
        zIndex:     1,
      }}>
        <span style={{
          fontSize:     12,
          fontWeight:   600,
          color:        '#1e293b',
          maxWidth:     NODE_INNER - 8,
          overflow:     'hidden',
          textOverflow: 'ellipsis',
          whiteSpace:   'nowrap',
        }}>
          {label}
        </span>
      </div>

      {/* ── Two invisible handles, both centered ───────────────────────── */}
      {/*
       * Self-loops need DISTINCT source and target handles on the same node.
       * ReactFlow blocks connecting a handle back to itself, but allows
       * source-id ≠ target-id even when source-node === target-node.
       *
       * Layout: target (NODE_OUTER) is slightly larger than source (NODE_INNER)
       * so releasing anywhere on the circle always hits the target handle,
       * while mouse-down always hits the source handle (on top in DOM order).
       */}
      <Handle
        type="target" id="tgt"
        position={Position.Top}
        style={{ ...handleStyle, width: NODE_OUTER + 6, height: NODE_OUTER + 6 }}
      />
      <Handle
        type="source" id="src"
        position={Position.Top}
        style={handleStyle}
      />
    </div>
  )
})
