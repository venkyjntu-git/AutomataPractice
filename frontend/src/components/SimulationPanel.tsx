/**
 * Run server-side simulation (custom input or full test suites) with
 * step-by-step playback and canvas state highlighting.
 */
import type { TestCase } from "@/api/questions"
import { useCallback, useEffect, useRef, useState } from "react"
import type {
  AutomataPayload,
  SimStep,
  SimulateRequestBody,
  SingleSimResult,
} from "@/api/submissions"
import { simulatePracticeAutomata } from "@/api/practice"

function stateIdFromStep(step: SimStep): string | null {
  if (step.state) return step.state
  if (step.active_states?.length) return step.active_states[0] ?? null
  return null
}

interface Props {
  questionId: number
  machine: string
  maxLength: number
  automata: AutomataPayload
  /** Public example tests (same order as server public_examples). */
  publicExamples: TestCase[]
  /** Private grading tests (same order as server test_cases). */
  gradingTests: TestCase[]
  /** Warn when exceeded; server default is 128 (AUTOMATA_MAX_STATES). */
  maxStatesLimit?: number
  practiceUserKey?: string | null
  onHighlightState: (stateId: string | null, pulse: number) => void
}

export default function SimulationPanel({
  questionId,
  machine,
  maxLength,
  automata,
  publicExamples,
  gradingTests,
  maxStatesLimit = 128,
  practiceUserKey,
  onHighlightState,
}: Props) {
  const [customInput, setCustomInput] = useState("")
  const [singleSuite, setSingleSuite] = useState<"public" | "private">("public")
  const singleList = singleSuite === "public" ? publicExamples : gradingTests
  const [singleIndex, setSingleIndex] = useState(0)
  const [runs, setRuns] = useState<SingleSimResult[] | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")
  const [selectedRun, setSelectedRun] = useState(0)
  const [stepIndex, setStepIndex] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [speedMs, setSpeedMs] = useState(600)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const clearHighlight = useCallback(() => {
    onHighlightState(null, Date.now())
  }, [onHighlightState])

  const currentRun = runs?.[selectedRun]

  useEffect(() => {
    if (!currentRun?.steps?.length) {
      clearHighlight()
      return
    }
    const step = currentRun.steps[Math.min(stepIndex, currentRun.steps.length - 1)]
    const sid = stateIdFromStep(step)
    onHighlightState(sid, Date.now())
  }, [currentRun, stepIndex, onHighlightState, clearHighlight])

  useEffect(() => {
    if (!playing) {
      if (intervalRef.current) {
        clearInterval(intervalRef.current)
        intervalRef.current = null
      }
      return
    }
    const run = runs?.[selectedRun]
    if (!run?.steps?.length) {
      setPlaying(false)
      return
    }
    intervalRef.current = setInterval(() => {
      setStepIndex((i) => {
        const max = run.steps.length - 1
        if (i >= max) {
          setPlaying(false)
          return i
        }
        return i + 1
      })
    }, speedMs)
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current)
        intervalRef.current = null
      }
    }
  }, [playing, runs, selectedRun, speedMs])

  useEffect(() => {
    setStepIndex(0)
  }, [selectedRun])

  useEffect(() => {
    setSingleIndex(0)
  }, [singleSuite])

  useEffect(() => {
    setSingleIndex((i) => {
      if (singleList.length === 0) return 0
      return Math.min(i, singleList.length - 1)
    })
  }, [singleList.length])

  useEffect(() => {
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
      clearHighlight()
    }
  }, [clearHighlight])

  async function runSim(body: SimulateRequestBody) {
    if (automata.states.length === 0) {
      setError("Draw at least one state on the canvas first.")
      return
    }
    if (!practiceUserKey) {
      setError("No practice session")
      return
    }
    setLoading(true)
    setError("")
    try {
      const out = await simulatePracticeAutomata(questionId, practiceUserKey, body)
      setRuns(out.runs)
      setSelectedRun(0)
      setStepIndex(0)
      setPlaying(false)
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } }; message?: string })
        ?.response?.data?.detail
      setError(typeof msg === "string" ? msg : "Simulation failed.")
      setRuns(null)
    } finally {
      setLoading(false)
    }
  }

  function handleCustom() {
    if (customInput.length > maxLength) {
      setError(`Input length must be ≤ ${maxLength}.`)
      return
    }
    void runSim({
      automata,
      mode: "custom_input",
      input: customInput,
    })
  }

  function handleSuite(suite: "public" | "private" | "all") {
    void runSim({
      automata,
      mode: "test_suite",
      suite,
    })
  }

  function handleSingleTest() {
    if (singleList.length === 0) {
      setError("No test cases in the selected suite.")
      return
    }
    const idx = Math.min(Math.max(0, singleIndex), singleList.length - 1)
    void runSim({
      automata,
      mode: "single_test",
      suite: singleSuite,
      test_index: idx,
    })
  }

  const steps = currentRun?.steps ?? []
  const step = steps[Math.min(stepIndex, Math.max(0, steps.length - 1))]

  return (
    <div className="flex min-h-0 flex-col gap-3 rounded-xl border border-slate-200 bg-slate-50/80 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
          Controls
        </h3>
        <p className="text-[10px] text-slate-400">
          NFA/PDA: trace is one witness path. Max input length {maxLength}.
        </p>
      </div>

      {automata.states.length > maxStatesLimit && (
        <p className="rounded border border-amber-200 bg-amber-50 px-2 py-1.5 text-xs text-amber-900">
          This diagram has {automata.states.length} states. The server rejects grading
          and simulation above {maxStatesLimit} states (set{" "}
          <span className="font-mono">AUTOMATA_MAX_STATES</span> on the API to raise the
          limit).
        </p>
      )}

      <div className="flex flex-wrap items-end gap-2">
        <div className="min-w-[12rem] flex-1">
          <label className="mb-1 block text-[10px] font-medium text-slate-500">
            Custom input (empty string allowed)
          </label>
          <input
            type="text"
            value={customInput}
            onChange={(e) => setCustomInput(e.target.value)}
            className="w-full rounded-lg border border-slate-200 bg-white px-2 py-1.5 font-mono text-xs text-slate-800"
            placeholder="ε or leave empty for empty string"
          />
        </div>
        <button
          type="button"
          disabled={loading}
          onClick={() => handleCustom()}
          className="rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-indigo-700 disabled:opacity-50"
        >
          {loading ? "Running…" : "Run custom"}
        </button>
      </div>

      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          disabled={loading}
          onClick={() => handleSuite("public")}
          className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
        >
          Run public examples
        </button>
        <button
          type="button"
          disabled={loading}
          onClick={() => handleSuite("private")}
          className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
        >
          Run private (grading) tests
        </button>
        <button
          type="button"
          disabled={loading}
          onClick={() => handleSuite("all")}
          className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
        >
          Run all tests
        </button>
      </div>

      <div className="border-t border-slate-200 pt-3">
        <p className="mb-2 text-[10px] font-semibold text-slate-600">
          Run one testcase
        </p>
        <div className="flex flex-wrap items-end gap-2">
          <div>
            <label className="mb-1 block text-[10px] font-medium text-slate-500">
              Suite
            </label>
            <select
              value={singleSuite}
              onChange={(e) =>
                setSingleSuite(e.target.value as "public" | "private")
              }
              className="rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-xs text-slate-800"
            >
              <option value="public">
                Public ({publicExamples.length})
              </option>
              <option value="private">
                Private ({gradingTests.length})
              </option>
            </select>
          </div>
          <div className="min-w-[12rem] flex-1">
            <label className="mb-1 block text-[10px] font-medium text-slate-500">
              Testcase
            </label>
            <select
              value={singleList.length === 0 ? 0 : singleIndex}
              disabled={singleList.length === 0}
              onChange={(e) => setSingleIndex(Number(e.target.value))}
              className="w-full max-w-md rounded-lg border border-slate-200 bg-white px-2 py-1.5 font-mono text-xs text-slate-800"
            >
              {singleList.length === 0 ? (
                <option value={0}>No tests</option>
              ) : (
                singleList.map((tc, i) => {
                  const preview =
                    tc.input.length > 48
                      ? `${tc.input.slice(0, 48)}…`
                      : tc.input
                  return (
                    <option key={`opt-${singleSuite}-${i}`} value={i}>
                      #{i + 1} · {tc.label} · {preview || "(empty)"}
                    </option>
                  )
                })
              )}
            </select>
          </div>
          <button
            type="button"
            disabled={loading || singleList.length === 0}
            onClick={() => handleSingleTest()}
            className="rounded-lg bg-violet-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-violet-700 disabled:opacity-50"
          >
            Run selected
          </button>
        </div>
      </div>

      {error && <p className="text-xs text-red-600">{error}</p>}

      {runs && runs.length > 0 && (
        <>
          <div className="max-h-32 overflow-y-auto rounded border border-slate-200 bg-white">
            <table className="w-full text-left text-[10px]">
              <thead className="sticky top-0 bg-slate-100 text-slate-500">
                <tr>
                  <th className="px-2 py-1">#</th>
                  <th className="px-2 py-1">Input</th>
                  <th className="px-2 py-1">Exp</th>
                  <th className="px-2 py-1">Got</th>
                  <th className="px-2 py-1">OK</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((r, i) => (
                  <tr
                    key={`sim-run-${i}-${r.expected ?? "x"}-${r.input.slice(0, 24)}`}
                    className={
                      i === selectedRun ? "bg-indigo-50" : "border-t border-slate-100"
                    }
                  >
                    <td className="px-2 py-1">
                      <button
                        type="button"
                        className="text-indigo-600 hover:underline"
                        onClick={() => setSelectedRun(i)}
                      >
                        {i + 1}
                      </button>
                    </td>
                    <td className="max-w-[10rem] truncate px-2 py-1 font-mono" title={r.input}>
                      {r.input}
                    </td>
                    <td className="px-2 py-1">{r.expected ?? "—"}</td>
                    <td className="px-2 py-1">{r.got}</td>
                    <td className="px-2 py-1">
                      {r.correct == null ? (
                        "—"
                      ) : r.correct ? (
                        <span className="text-green-600">✓</span>
                      ) : (
                        <span className="text-red-600">✗</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {currentRun && (
            <div className="space-y-2 rounded-lg border border-slate-200 bg-white p-3">
              <div className="flex flex-wrap items-center gap-2 text-[10px] text-slate-600">
                <span>
                  String:{" "}
                  <span className="font-mono text-slate-800">{currentRun.input}</span>
                </span>
                {currentRun.expected != null && (
                  <span>
                    expected {currentRun.expected} · got {currentRun.got}
                  </span>
                )}
              </div>
              <p className="text-[10px] text-slate-500">{currentRun.final_reason}</p>

              <div className="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  className="rounded border border-slate-300 bg-slate-50 px-2 py-1 text-[10px] font-medium text-slate-700 hover:bg-slate-100"
                  onClick={() => {
                    setStepIndex((i) => Math.max(0, i - 1))
                    setPlaying(false)
                  }}
                >
                  Step back
                </button>
                <button
                  type="button"
                  className="rounded border border-slate-300 bg-slate-50 px-2 py-1 text-[10px] font-medium text-slate-700 hover:bg-slate-100"
                  onClick={() => {
                    setStepIndex((i) => Math.min(steps.length - 1, i + 1))
                    setPlaying(false)
                  }}
                  disabled={steps.length === 0}
                >
                  Step forward
                </button>
                <button
                  type="button"
                  className="rounded bg-emerald-600 px-2 py-1 text-[10px] font-semibold text-white hover:bg-emerald-700"
                  onClick={() => {
                    if (stepIndex >= steps.length - 1) setStepIndex(0)
                    setPlaying(true)
                  }}
                  disabled={steps.length === 0}
                >
                  Play
                </button>
                <button
                  type="button"
                  className="rounded bg-slate-700 px-2 py-1 text-[10px] font-semibold text-white hover:bg-slate-800"
                  onClick={() => setPlaying(false)}
                >
                  Stop
                </button>
                <button
                  type="button"
                  className="rounded border border-slate-300 bg-white px-2 py-1 text-[10px] font-medium text-slate-700 hover:bg-slate-50"
                  onClick={() => {
                    setStepIndex(0)
                    setPlaying(false)
                  }}
                >
                  Reset
                </button>
                <label className="flex items-center gap-1 text-[10px] text-slate-500">
                  Speed
                  <input
                    type="range"
                    min={200}
                    max={1800}
                    step={100}
                    value={speedMs}
                    onChange={(e) => setSpeedMs(Number(e.target.value))}
                  />
                  <span>{speedMs}ms</span>
                </label>
                <span className="text-[10px] text-slate-400">
                  Step {Math.min(stepIndex + 1, Math.max(1, steps.length))} / {steps.length}
                </span>
              </div>

              {step && (
                <div className="rounded border border-slate-100 bg-slate-50 px-2 py-2 font-mono text-[10px] leading-relaxed text-slate-700">
                  <div className="mb-1 text-[9px] uppercase text-slate-400">
                    {step.kind} · {step.note}
                  </div>
                  {machine === "PDA" && step.stack && (
                    <div className="mb-1 flex gap-2">
                      <span className="text-slate-500">Stack (bottom→top):</span>
                      <span>{step.stack.join(" ") || "ε"}</span>
                    </div>
                  )}
                  {machine === "TM" && step.tape && step.head != null && (
                    <div className="flex flex-wrap items-center gap-1">
                      <span className="text-slate-500">Tape:</span>
                      {step.tape.map((cell, i) => (
                        <span
                          key={`${i}-${cell}`}
                          className={
                            i === step.head
                              ? "rounded border-2 border-amber-500 bg-amber-50 px-1"
                              : "rounded border border-slate-200 px-1"
                          }
                        >
                          {cell === "_" ? "␣" : cell}
                        </span>
                      ))}
                      <span className="text-slate-400">head={step.head}</span>
                    </div>
                  )}
                  {(machine === "DFA" || machine === "NFA") && (
                    <div>
                      <span className="text-slate-500">Remaining:</span>{" "}
                      <span className="text-slate-800">
                        {step.remaining_input === "" ? "ε" : step.remaining_input}
                      </span>
                      {step.active_states && step.active_states.length > 0 && (
                        <span className="ml-2 text-slate-500">
                          states [{step.active_states.join(", ")}]
                        </span>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  )
}
