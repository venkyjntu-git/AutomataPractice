/**
 * AutomataCanvas — JFLAP-style automaton editor built on @xyflow/react v12.
 *
 * ┌──────────────────────────────────────────────────────────┐
 * │  [↖ Select]  [○ State]  [→ Transition]  [✕ Delete]      │  ← toolbar
 * ├──────────────────────────────────────────────────────────┤
 * │                                                          │
 * │          (canvas — ReactFlow)                            │
 * │                                                          │
 * └──────────────────────────────────────────────────────────┘
 *
 * Modes (like JFLAP tools):
 *   select     — drag states to move; double-click state = rename;
 *                double-click edge = edit transition; Delete key removes selected
 *   state      — click empty canvas → create auto-named state (q0, q1, …)
 *   transition — drag between state handles → TransitionDialog appears
 *   delete     — click state or transition → delete immediately
 *
 * Right-click state (any mode) → context menu: toggle accept / set initial / delete.
 */
import {
  Background,
  ConnectionMode,
  Controls,
  MiniMap,
  ReactFlow,
  addEdge,
  applyNodeChanges,
  useEdgesState,
  useNodesState,
  type Connection,
  type Edge,
  type NodeChange,
  type Node,
  type ReactFlowInstance,
} from "@xyflow/react"
import "@xyflow/react/dist/style.css"
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react"

import type { AutomataPayload, AutomataTransition } from "@/api/submissions"
import StateNode from "./StateNode"
import TransitionDialog, { type TransitionFields } from "./TransitionDialog"
import TransitionEdge, { type TransitionEdgeData } from "./TransitionEdge"

// ── Types ─────────────────────────────────────────────────────────────────────

type Mode = "select" | "state" | "transition" | "delete"

interface CtxMenu {
  nodeId: string
  x: number
  y: number
}
interface PendingTx {
  connection: Connection
}
interface EditingTx {
  edgeId: string
  currentData: TransitionEdgeData
}

// ── Constants ─────────────────────────────────────────────────────────────────

const NODE_TYPES = { state: StateNode }
const EDGE_TYPES = { transition: TransitionEdge }

const TOOLS: {
  mode: Mode
  label: string
  hint: string
  icon: React.ReactNode
}[] = [
  {
    mode: "select",
    label: "Select",
    hint: "Move states · Double-click to rename/edit",
    icon: (
      <svg viewBox="0 0 16 16" width="14" height="14" fill="currentColor">
        <path d="M3 1l10 6-5 1.5L6.5 13z" />
      </svg>
    ),
  },
  {
    mode: "state",
    label: "State",
    hint: "Click canvas to add a state",
    icon: (
      <svg
        viewBox="0 0 16 16"
        width="14"
        height="14"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
      >
        <circle cx="8" cy="8" r="6" />
      </svg>
    ),
  },
  {
    mode: "transition",
    label: "Transition",
    hint: "Drag from handle to handle",
    icon: (
      <svg
        viewBox="0 0 16 16"
        width="14"
        height="14"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
      >
        <path d="M2 8 Q8 2 14 8" />
        <polyline points="11,5 14,8 11,11" fill="none" />
      </svg>
    ),
  },
  {
    mode: "delete",
    label: "Delete",
    hint: "Click state or transition to delete",
    icon: (
      <svg
        viewBox="0 0 16 16"
        width="14"
        height="14"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
      >
        <line x1="3" y1="3" x2="13" y2="13" />
        <line x1="13" y1="3" x2="3" y2="13" />
      </svg>
    ),
  },
]

// Next available state label: q0, q1, … (reuses deleted labels)
function nextLabel(nodes: Node[]): string {
  const labels = new Set(
    nodes.map((n) => String((n.data as Record<string, unknown>).label))
  )
  for (let i = 0; ; i++) {
    if (!labels.has(`q${i}`)) return `q${i}`
  }
}

let _uid = 0
const uid = () => `s${_uid++}`

function payloadToFlow(machine: string, payload: AutomataPayload): {
  nodes: Node[]
  edges: Edge[]
} {
  const noop = () => {}
  const states = payload.states || []
  const nodes: Node[] = states.map((s, i) => ({
    id: s.id,
    type: "state",
    position: {
      x: 80 + (i % 5) * 200,
      y: 80 + Math.floor(i / 5) * 140,
    },
    data: {
      label: s.label ?? s.id,
      initial: s.initial,
      accept: s.accept,
      connectMode: false,
    },
  }))

  const transitions = payload.transitions || []
  const edges: Edge[] = transitions.map((t, idx) => {
    const fields: TransitionFields = {
      symbol: t.symbol ?? "ε",
      stack_top: t.stack_top,
      stack_push: t.stack_push,
      write: t.write,
      direction: t.direction,
    }
    const data: TransitionEdgeData = {
      machine,
      symbol: fields.symbol,
      stack_top: fields.stack_top,
      stack_push: fields.stack_push,
      write: fields.write,
      direction: fields.direction,
      onDelete: noop,
      onEdit: noop,
      onOffsetChange: noop,
    }
    return {
      id: `loaded-${idx}-${t.from_state}-${t.to_state}`,
      source: t.from_state,
      target: t.to_state,
      type: "transition",
      data,
    } as unknown as Edge
  })
  return { nodes, edges }
}

// ── Component ─────────────────────────────────────────────────────────────────

interface Props {
  machine: string
  alphabet: string[]
  onChange: (automata: AutomataPayload) => void
  /** Load a saved diagram (e.g. past submission). Parent should remount with key when switching. */
  initialAutomata?: AutomataPayload | null
  readOnly?: boolean
  /** Highlight the state node whose id matches (simulation playback). */
  activeStateId?: string | null
  /** Bump to re-trigger highlight animation when stepping the same state twice. */
  simulationStepPulse?: number
  /** Allow dragging node positions while still keeping the diagram non-editable. */
  allowStateRepositionInReadOnly?: boolean
}

export default function AutomataCanvas({
  machine,
  alphabet,
  onChange,
  initialAutomata,
  readOnly = false,
  activeStateId = null,
  simulationStepPulse = 0,
  allowStateRepositionInReadOnly = false,
}: Props) {
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([])
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([])
  const [mode, setMode] = useState<Mode>("select")
  const [menu, setMenu] = useState<CtxMenu | null>(null)
  const [pendingTx, setPendingTx] = useState<PendingTx | null>(null)
  const [editingTx, setEditingTx] = useState<EditingTx | null>(null)
  const rfRef = useRef<ReactFlowInstance | null>(null)
  const wrapperRef = useRef<HTMLDivElement>(null)
  /** Avoid infinite parent↔child loops when `onChange` is an inline function each render. */
  const onChangeRef = useRef(onChange)
  useLayoutEffect(() => {
    onChangeRef.current = onChange
  }, [onChange])
  /** Skip re-applying the same readOnly payload when the parent passes a new object reference. */
  const lastReadonlyInitialSig = useRef<string>("")

  const handleNodesChange = useCallback(
    (changes: NodeChange<Node>[]) => {
      if (!readOnly) {
        onNodesChange(changes)
        return
      }
      if (!allowStateRepositionInReadOnly) return
      const positionOnly = changes.filter(
        (c) => c.type === "position" || c.type === "dimensions"
      )
      if (positionOnly.length === 0) return
      setNodes((ns) => applyNodeChanges(positionOnly, ns))
    },
    [readOnly, allowStateRepositionInReadOnly, onNodesChange, setNodes]
  )

  useEffect(() => {
    if (!readOnly || !initialAutomata?.states?.length) {
      lastReadonlyInitialSig.current = ""
      return
    }
    let sig: string
    try {
      sig = JSON.stringify(initialAutomata)
    } catch {
      sig = ""
    }
    if (sig && lastReadonlyInitialSig.current === sig) return
    lastReadonlyInitialSig.current = sig
    const { nodes: n, edges: e } = payloadToFlow(machine, initialAutomata)
    setNodes(n)
    setEdges(e)
    queueMicrotask(() => rfRef.current?.fitView({ padding: 0.2 }))
  }, [readOnly, initialAutomata, machine, setNodes, setEdges])

  // Edit mode: seed once from initialAutomata while the graph is still empty (parent can remount with key to reset).
  useEffect(() => {
    if (readOnly || !initialAutomata?.states?.length) return
    if (nodes.length > 0 || edges.length > 0) return
    const { nodes: n, edges: e } = payloadToFlow(machine, initialAutomata)
    setNodes(n)
    setEdges(e)
    queueMicrotask(() => rfRef.current?.fitView({ padding: 0.2 }))
  }, [readOnly, initialAutomata, machine, nodes.length, edges.length, setNodes, setEdges])

  // ── Simulation: mark active state for highlight ───────────────────────────
  useEffect(() => {
    if (nodes.length === 0) return
    setNodes((ns) => {
      let changed = false
      const next = ns.map((n) => {
        const d = n.data as Record<string, unknown>
        const want = activeStateId != null && n.id === activeStateId
        if (Boolean(d.simActive) === want && Number(d.simPulse ?? 0) === simulationStepPulse) {
          return n
        }
        changed = true
        return {
          ...n,
          data: {
            ...d,
            simActive: want,
            simPulse: simulationStepPulse,
          },
        }
      })
      return changed ? next : ns
    })
  }, [activeStateId, simulationStepPulse, setNodes, nodes.length])

  // ── Sync connectMode into every node when mode changes ───────────────────
  // connectMode=true  → handles accept pointer events (TRANSITION tool)
  // connectMode=false → handles are inert, so clicks reach the node correctly
  useEffect(() => {
    if (readOnly) return
    const wantConnect = mode === "transition"
    setNodes((ns) => {
      if (ns.length === 0) return ns
      if (
        ns.every(
          (n) => Boolean((n.data as Record<string, unknown>).connectMode) === wantConnect
        )
      ) {
        return ns
      }
      return ns.map((n) => ({
        ...n,
        data: { ...n.data, connectMode: wantConnect },
      }))
    })
  }, [mode, setNodes, readOnly])

  // ── Emit serialised automata to parent ────────────────────────────────────
  useEffect(() => {
    const states = nodes.map((n) => {
      const d = n.data as Record<string, unknown>
      return {
        id: n.id,
        label: String(d.label ?? n.id),
        initial: Boolean(d.initial),
        accept: Boolean(d.accept),
      }
    })
    const transitions: AutomataTransition[] = edges.map((e) => {
      const d = e.data as Record<string, unknown>
      const t: AutomataTransition = {
        from_state: e.source,
        to_state: e.target,
        symbol: String(d?.symbol ?? "ε"),
      }
      if (machine === "PDA") {
        t.stack_top = String(d?.stack_top ?? "ε")
        t.stack_push = String(d?.stack_push ?? "ε")
      } else if (machine === "TM") {
        t.write = String(d?.write ?? d?.symbol ?? "ε")
        t.direction = String(d?.direction ?? "R")
      }
      return t
    })
    if (!readOnly) onChangeRef.current({ states, transitions })
  }, [nodes, edges, machine, readOnly])

  // ── State mutations ───────────────────────────────────────────────────────
  const toggleAccept = useCallback(
    (id: string) => {
      setNodes((ns) =>
        ns.map((n) =>
          n.id === id
            ? {
                ...n,
                data: {
                  ...n.data,
                  accept: !(n.data as Record<string, unknown>).accept,
                },
              }
            : n
        )
      )
    },
    [setNodes]
  )

  const setInitialState = useCallback(
    (id: string) => {
      setNodes((ns) =>
        ns.map((n) => ({
          ...n,
          data: { ...n.data, initial: n.id === id },
        }))
      )
    },
    [setNodes]
  )

  const deleteStateById = useCallback(
    (id: string) => {
      setNodes((ns) => ns.filter((n) => n.id !== id))
      setEdges((es) => es.filter((e) => e.source !== id && e.target !== id))
      setMenu(null)
    },
    [setNodes, setEdges]
  )

  const renameState = useCallback(
    (id: string) => {
      setNodes((ns) => {
        const node = ns.find((n) => n.id === id)
        const current = String(
          (node?.data as Record<string, unknown>)?.label ?? ""
        )
        const next = window.prompt("Rename state:", current)
        if (!next?.trim()) return ns
        return ns.map((n) =>
          n.id === id ? { ...n, data: { ...n.data, label: next.trim() } } : n
        )
      })
    },
    [setNodes]
  )

  // ── Edge mutations ────────────────────────────────────────────────────────
  const deleteEdgeById = useCallback(
    (id: string) => {
      setEdges((es) => es.filter((e) => e.id !== id))
    },
    [setEdges]
  )

  const updateEdgeFields = useCallback(
    (id: string, fields: TransitionFields) => {
      setEdges((es) =>
        es.map((e) =>
          e.id === id ? { ...e, data: { ...e.data, ...fields } } : e
        )
      )
    },
    [setEdges]
  )

  const updateEdgeLabelOffset = useCallback(
    (id: string, x: number, y: number) => {
      setEdges((es) =>
        es.map((e) =>
          e.id === id
            ? { ...e, data: { ...e.data, labelOffsetX: x, labelOffsetY: y } }
            : e
        )
      )
    },
    [setEdges]
  )

  const openEdgeEdit = useCallback(
    (edgeId: string) => {
      setEdges((es) => {
        const edge = es.find((e) => e.id === edgeId)
        if (edge)
          setEditingTx({
            edgeId,
            currentData: edge.data as unknown as TransitionEdgeData,
          })
        return es
      })
    },
    [setEdges]
  )

  // Build edge data (stable callbacks — no closures over changing state)
  const makeEdgeData = useCallback(
    (fields: TransitionFields) => ({
      machine,
      ...fields,
      onDelete: deleteEdgeById,
      onEdit: openEdgeEdit,
      onOffsetChange: updateEdgeLabelOffset,
    }),
    [machine, deleteEdgeById, openEdgeEdit, updateEdgeLabelOffset]
  )

  // ── Add state (STATE mode: click on canvas) ───────────────────────────────
  const addStateAt = useCallback(
    (screenX: number, screenY: number) => {
      const pos = rfRef.current?.screenToFlowPosition({
        x: screenX,
        y: screenY,
      }) ?? { x: 150 + Math.random() * 200, y: 150 + Math.random() * 100 }
      setNodes((ns) => {
        const label = nextLabel(ns)
        const isFirst = ns.length === 0
        const node: Node = {
          id: uid(),
          type: "state",
          position: pos,
          data: { label, accept: false, initial: isFirst, connectMode: false },
        }
        return [...ns, node]
      })
    },
    [setNodes]
  )

  // ── ReactFlow event handlers ──────────────────────────────────────────────

  // Pane click — only active in STATE mode
  const onPaneClick = useCallback(
    (e: React.MouseEvent) => {
      setMenu(null)
      if (mode === "state") addStateAt(e.clientX, e.clientY)
    },
    [mode, addStateAt]
  )

  // Node click — DELETE mode deletes; other modes do nothing extra
  const onNodeClick = useCallback(
    (_e: React.MouseEvent, node: Node) => {
      if (mode === "delete") deleteStateById(node.id)
    },
    [mode, deleteStateById]
  )

  // Edge click — DELETE mode deletes
  const onEdgeClick = useCallback(
    (_e: React.MouseEvent, edge: Edge) => {
      if (mode === "delete") deleteEdgeById(edge.id)
    },
    [mode, deleteEdgeById]
  )

  // Node double-click — open self-loop TransitionDialog (any mode)
  const onNodeDoubleClick = useCallback((_e: React.MouseEvent, node: Node) => {
    setPendingTx({
      connection: {
        source: node.id,
        target: node.id,
        sourceHandle: "src",
        targetHandle: "tgt",
      },
    })
  }, [])

  // Edge double-click — open edit dialog (SELECT mode)
  const onEdgeDoubleClick = useCallback((_e: React.MouseEvent, edge: Edge) => {
    const d = edge.data as unknown as TransitionEdgeData
    setEditingTx({ edgeId: edge.id, currentData: d })
  }, [])

  // Connect — only fires in TRANSITION mode (nodesConnectable)
  const onConnect = useCallback((connection: Connection) => {
    setPendingTx({ connection })
  }, [])

  // Right-click → context menu
  const onNodeContextMenu = useCallback((e: React.MouseEvent, node: Node) => {
    e.preventDefault()
    setMenu({ nodeId: node.id, x: e.clientX, y: e.clientY })
  }, [])

  const closeMenu = useCallback(() => setMenu(null), [])

  // ── TransitionDialog confirm/cancel ───────────────────────────────────────
  const handleNewTransitionConfirm = useCallback(
    (fields: TransitionFields) => {
      if (!pendingTx) return
      const { connection } = pendingTx
      const edge: Edge = {
        id: `e-${connection.source}-${connection.target}-${Date.now()}`,
        source: connection.source!,
        target: connection.target!,
        type: "transition",
        data: makeEdgeData(fields),
      }
      const isSelfLoop = connection.source === connection.target
      // addEdge deduplicates by source+target+sourceHandle+targetHandle, which
      // would replace an existing self-loop instead of adding a second one.
      // Bypass it for self-loops so multiple self-loops on the same state work.
      setEdges((es) => (isSelfLoop ? [...es, edge] : addEdge(edge, es)))
      setPendingTx(null)
    },
    [pendingTx, makeEdgeData, setEdges]
  )

  const handleEditTransitionConfirm = useCallback(
    (fields: TransitionFields) => {
      if (!editingTx) return
      updateEdgeFields(editingTx.edgeId, fields)
      setEditingTx(null)
    },
    [editingTx, updateEdgeFields]
  )

  // ── Derived menu state ────────────────────────────────────────────────────
  const menuNode = menu ? nodes.find((n) => n.id === menu.nodeId) : null
  const menuAccept = Boolean(
    (menuNode?.data as Record<string, unknown>)?.accept
  )
  const menuInitial = Boolean(
    (menuNode?.data as Record<string, unknown>)?.initial
  )

  // ── Cursor style per mode ─────────────────────────────────────────────────
  const cursors: Record<Mode, string> = {
    select: "default",
    state: "crosshair",
    transition: "crosshair",
    delete: "not-allowed",
  }

  return (
    <div
      className="flex flex-col overflow-hidden rounded-xl border border-slate-200 bg-white"
      style={{ height: "100%", minHeight: 480 }}
    >
      {readOnly && (
        <div className="shrink-0 border-b border-amber-200 bg-amber-50 px-3 py-1.5 text-center text-xs font-medium text-amber-900">
          View only — submission preview
        </div>
      )}
      {/* ── JFLAP-style toolbar ─────────────────────────────────────────── */}
      <div
        className={`flex shrink-0 items-center gap-1 border-b border-slate-200 bg-slate-100 px-2 py-1.5 ${readOnly ? "hidden" : ""}`}
      >
        {TOOLS.map((t) => (
          <button
            key={t.mode}
            title={t.hint}
            onClick={() => setMode(t.mode)}
            className={[
              "flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium transition-all",
              mode === t.mode
                ? "border-blue-700 bg-blue-600 text-white shadow-inner"
                : "border-slate-300 bg-white text-slate-600 hover:border-slate-400 hover:bg-slate-50",
            ].join(" ")}
          >
            {t.icon}
            {t.label}
          </button>
        ))}

        {/* Separator + current mode hint */}
        <span className="ml-3 hidden text-xs text-slate-400 italic sm:block">
          {TOOLS.find((t) => t.mode === mode)?.hint}
        </span>

        {/* Alphabet badge */}
        <span className="ml-auto rounded border border-slate-200 bg-white px-2 py-0.5 text-xs text-slate-500">
          Σ = {"{" + alphabet.join(", ") + "}"}
        </span>
      </div>

      {/* ── ReactFlow canvas ────────────────────────────────────────────── */}
      <div
        ref={wrapperRef}
        className="relative flex-1"
        style={{ minHeight: 0, cursor: readOnly ? "default" : cursors[mode] }}
        onClick={closeMenu}
      >
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={NODE_TYPES}
          edgeTypes={EDGE_TYPES}
          onNodesChange={handleNodesChange}
          onEdgesChange={readOnly ? () => {} : onEdgesChange}
          onConnect={readOnly ? undefined : onConnect}
          onPaneClick={readOnly ? undefined : onPaneClick}
          onNodeClick={readOnly ? undefined : onNodeClick}
          onEdgeClick={readOnly ? undefined : onEdgeClick}
          onNodeDoubleClick={readOnly ? undefined : onNodeDoubleClick}
          onEdgeDoubleClick={readOnly ? undefined : onEdgeDoubleClick}
          onNodeContextMenu={readOnly ? undefined : onNodeContextMenu}
          onInit={(inst) => {
            rfRef.current = inst
          }}
          connectionMode={ConnectionMode.Loose}
          isValidConnection={() => true}
          nodesConnectable={!readOnly && mode === "transition"}
          nodesDraggable={(!readOnly && mode === "select") || allowStateRepositionInReadOnly}
          elementsSelectable={!readOnly && mode === "select"}
          deleteKeyCode={!readOnly && mode === "select" ? "Delete" : null}
          fitView={false}
          style={{ width: "100%", height: "100%" }}
        >
          {/* Arrowhead markers */}
          <svg style={{ position: "absolute", width: 0, height: 0 }}>
            <defs>
              <marker
                id="arrowhead"
                markerWidth="10"
                markerHeight="7"
                refX="9"
                refY="3.5"
                orient="auto"
              >
                <polygon points="0 0, 10 3.5, 0 7" fill="#374151" />
              </marker>
              <marker
                id="arrowhead-selected"
                markerWidth="10"
                markerHeight="7"
                refX="9"
                refY="3.5"
                orient="auto"
              >
                <polygon points="0 0, 10 3.5, 0 7" fill="#3b82f6" />
              </marker>
            </defs>
          </svg>

          <Background gap={24} color="#e2e8f0" />
          <Controls showInteractive={false} />
          <MiniMap zoomable pannable nodeColor="#e2e8f0" />
        </ReactFlow>

        {/* ── Context menu ─────────────────────────────────────────────── */}
        {menu && menuNode && (
          <div
            className="fixed z-50 min-w-[200px] rounded-xl border border-slate-200 bg-white py-1.5 text-sm shadow-2xl"
            style={{ left: menu.x, top: menu.y }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-1 border-b border-slate-100 px-4 py-1.5 text-xs font-semibold tracking-wide text-slate-400 uppercase">
              State: {String((menuNode.data as Record<string, unknown>).label)}
            </div>
            <button
              className="w-full px-4 py-2 text-left text-sm text-slate-700 hover:bg-slate-50"
              onClick={() => {
                toggleAccept(menu.nodeId)
                closeMenu()
              }}
            >
              {menuAccept
                ? "◎  Remove accept state"
                : "◎  Mark as accept state"}
            </button>
            <button
              className="w-full px-4 py-2 text-left text-sm text-slate-700 hover:bg-slate-50"
              disabled={menuInitial}
              onClick={() => {
                setInitialState(menu.nodeId)
                closeMenu()
              }}
            >
              {menuInitial
                ? "→  Initial state (current)"
                : "→  Set as initial state"}
            </button>
            <button
              className="w-full px-4 py-2 text-left text-sm text-slate-700 hover:bg-slate-50"
              onClick={() => {
                renameState(menu.nodeId)
                closeMenu()
              }}
            >
              ✎ Rename state
            </button>
            <hr className="my-1 border-slate-100" />
            <button
              className="w-full px-4 py-2 text-left text-sm text-red-500 hover:bg-red-50"
              onClick={() => deleteStateById(menu.nodeId)}
            >
              ✕ Delete state
            </button>
          </div>
        )}
      </div>

      {/* ── TransitionDialog — new transition ────────────────────────── */}
      {pendingTx && !readOnly && (
        <TransitionDialog
          machine={machine}
          onConfirm={handleNewTransitionConfirm}
          onCancel={() => setPendingTx(null)}
        />
      )}

      {/* ── TransitionDialog — edit existing transition ───────────────── */}
      {editingTx && !readOnly && (
        <TransitionDialog
          machine={machine}
          initial={{
            symbol: editingTx.currentData.symbol,
            stack_top: editingTx.currentData.stack_top,
            stack_push: editingTx.currentData.stack_push,
            write: editingTx.currentData.write,
            direction: editingTx.currentData.direction,
          }}
          onConfirm={handleEditTransitionConfirm}
          onCancel={() => setEditingTx(null)}
        />
      )}
    </div>
  )
}
