import AutomataCanvas from "@/components/AutomataCanvas"
import { getAutomataViewerSnapshot } from "@/utils/automataViewerSession"
import { useEffect, useMemo, useState } from "react"
import { useNavigate, useParams } from "react-router-dom"
import type { AutomataViewerSnapshot } from "@/utils/automataViewerSession"

export default function AutomataViewerPage() {
  const navigate = useNavigate()
  const { token } = useParams<{ token: string }>()
  const [snapshot, setSnapshot] = useState<AutomataViewerSnapshot | null>(null)

  useEffect(() => {
    if (!token) {
      setSnapshot(null)
      return
    }
    setSnapshot(getAutomataViewerSnapshot(token))
  }, [token])

  const machine = snapshot?.machine ?? "DFA"
  const alphabet = snapshot?.alphabet ?? []
  const automata = snapshot?.automata ?? null
  const title = snapshot?.title ?? "Automata Viewer"

  const hasAutomata = useMemo(
    () => Boolean(automata && automata.states.length > 0),
    [automata]
  )
  return (
    <div className="min-h-screen bg-slate-50">
      <header className="flex items-center justify-between border-b border-slate-200 bg-white px-6 py-4">
        <h1 className="text-base font-semibold text-slate-800">{title}</h1>
        <button
          type="button"
          onClick={() => navigate(-1)}
          className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50"
        >
          Back
        </button>
      </header>
      <main className="mx-auto max-w-6xl p-6">
        <div className="mb-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600">
          View-only mode: drag states to reposition layout for readability.
        </div>
        <div className="h-[calc(100vh-10.5rem)] min-h-[360px] rounded-xl border border-slate-200 bg-white p-2">
          {hasAutomata ? (
            <AutomataCanvas
              key={token ?? "no-token"}
              alphabet={alphabet}
              machine={machine}
              readOnly
              allowStateRepositionInReadOnly
              initialAutomata={automata}
              onChange={() => {}}
            />
          ) : (
            <div className="flex h-full items-center justify-center text-sm text-slate-500">
              No automata data available for this view.
            </div>
          )}
        </div>
      </main>
    </div>
  )
}
