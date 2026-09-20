import type { Question } from "@/api/questions"
import type {
  AutomataPayload,
  PastSubmission,
  SubmissionResult,
} from "@/api/submissions"
import { createAutomataViewerSnapshot } from "@/utils/automataViewerSession"
import AutomataCanvas from "./AutomataCanvas"
import SimulationPanel from "./SimulationPanel"
import { useCallback, useState } from "react"
import { useNavigate } from "react-router-dom"

interface Props {
  question: Question | null
  history: PastSubmission[]
  result: SubmissionResult | null
  submitting: boolean
  error: string
  /** Current diagram (for simulation and submit). */
  automata: AutomataPayload
  onCanvasChange: (automata: AutomataPayload) => void
  onBack: () => void
  onSubmit: () => void
  /** Practice: session key for simulate API. */
  practiceUserKey?: string | null
  /** After a graded submit, optional navigation to another question */
  onNextQuestion?: () => void
  /** When true, a "next" question exists in this flow (assignment or practice). */
  showNextNav?: boolean
  /** When true, Next is only enabled after a graded result (practice). */
  nextRequiresResult?: boolean
  /** Practice: allow Next before any submission (still uses prefs to generate). */
  allowNextWithoutSubmit?: boolean
  onPreviousQuestion?: () => void
  /** When true, show Previous question (assignment or practice stack). */
  showPrevNav?: boolean
  /** Course assignment: e.g. "Assignment · slot 1 (1 of 2)" */
  assignmentSummary?: string
  /** Load a past submission diagram into the editable canvas. */
  onLoadSubmission?: (submission: PastSubmission) => void
  /** Bump with each explicit “load into canvas” so AutomataCanvas remounts and hydrates from `automata`. */
  canvasRemountKey?: number
}



const MACHINE_COLORS: Record<string, string> = {
  DFA: "bg-blue-100 text-blue-800",
  NFA: "bg-purple-100 text-purple-800",
  PDA: "bg-green-100 text-green-800",
  TM: "bg-orange-100 text-orange-800",
}

export default function QuestionAnswerComponent({
  question,
  history,
  result,
  submitting,
  error,
  automata,
  onBack,
  onCanvasChange,
  onSubmit,
  onNextQuestion,
  showNextNav = false,
  nextRequiresResult = false,
  allowNextWithoutSubmit,
  practiceUserKey,
  onPreviousQuestion,
  showPrevNav = false,
  assignmentSummary,
  onLoadSubmission,
  canvasRemountKey = 0,
}: Props) {
  const navigate = useNavigate()
  const [simHighlight, setSimHighlight] = useState<{ id: string | null; pulse: number }>({
    id: null,
    pulse: 0,
  })
  const [resultsTab, setResultsTab] = useState<"simulation" | "submission">("simulation")

  const onSimulationHighlight = useCallback((stateId: string | null, pulse: number) => {
    setSimHighlight({ id: stateId, pulse })
  }, [])

  const showNextButton = Boolean(
    onNextQuestion &&
      showNextNav &&
      (!nextRequiresResult || Boolean(result) || Boolean(allowNextWithoutSubmit))
  )
  const showPrevButton = Boolean(onPreviousQuestion && showPrevNav)

  const openSubmissionViewer = useCallback(
    (s: PastSubmission) => {
      if (!s.automata_json || !question) return
      const token = createAutomataViewerSnapshot({
        title: `Submission · ${new Date(s.submitted_at).toLocaleString()}`,
        machine: question.machine,
        alphabet: question.alphabet,
        automata: s.automata_json,
      })
      navigate(`/automata/viewer/${token}`)
    },
    [navigate, question]
  )

  if (!question) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50">
        <p className="text-slate-400">Loading question…</p>
      </div>
    )
  }

  const examples = question.public_examples ?? []
  const gradingTests = question.grading_tests ?? []

  const tabBtn = (active: boolean) =>
    [
      "rounded-t-lg px-4 py-2 text-xs font-semibold transition",
      active
        ? "border border-b-0 border-slate-200 bg-white text-indigo-700"
        : "border border-transparent text-slate-500 hover:text-slate-800",
    ].join(" ")

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-slate-50">
      <header className="flex flex-wrap items-center gap-4 border-b border-slate-200 bg-white px-6 py-3">
        <button
          onClick={onBack}
          className="text-sm text-slate-400 hover:text-slate-700"
        >
          ← Back
        </button>
        <span
          className={`rounded-full px-2 py-0.5 text-xs font-medium ${MACHINE_COLORS[question.machine] ?? "bg-slate-100 text-slate-600"}`}
        >
          {question.machine}
        </span>
        {question.is_closure && (
          <span className="rounded-full bg-yellow-100 px-2 py-0.5 text-xs font-medium text-yellow-800">
            Closure
          </span>
        )}
        {question.difficulty && (
          <span className="text-xs text-slate-400">{question.difficulty}</span>
        )}
        {assignmentSummary && (
          <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600">
            {assignmentSummary}
          </span>
        )}
      </header>

      <div className="flex flex-1 overflow-hidden">
        <aside className="flex w-80 min-w-[20rem] flex-col overflow-y-auto border-r border-slate-200 bg-white">
          <div className="border-b border-slate-100 p-6">
            <h2 className="mb-3 text-sm font-semibold text-slate-700">
              Question
            </h2>
            <p className="text-sm leading-relaxed text-slate-700">
              {question.text}
            </p>

            <div className="mt-4 space-y-1 text-xs text-slate-500">
              <p>
                <span className="font-medium">Alphabet:</span>{" "}
                {"{" + question.alphabet.join(", ") + "}"}
              </p>
              <p>
                <span className="font-medium">Max length:</span>{" "}
                {question.max_length}
              </p>
              <p>
                <span className="font-medium">Machine:</span> {question.machine}
              </p>
            </div>
          </div>

          {examples.length > 0 && (
            <div className="border-b border-slate-100 p-6">
              <h3 className="mb-2 text-xs font-semibold uppercase text-slate-500">
                Example test cases
              </h3>
              <p className="mb-2 text-xs text-slate-400">
                Public examples — full grading suite is available in Simulation → Run
                private tests.
              </p>
              <ul className="space-y-2">
                {examples.map((tc, i) => (
                  <li
                    key={`${tc.input}-${i}`}
                    className="rounded-lg border border-slate-100 bg-slate-50 px-3 py-2 text-xs"
                  >
                    <span
                      className={
                        tc.label === "ACCEPT"
                          ? "font-semibold text-green-700"
                          : "font-semibold text-red-600"
                      }
                    >
                      {tc.label === "ACCEPT" ? "Accept" : "Reject"}
                    </span>
                    <span className="text-slate-400"> · </span>
                    <span
                      className="inline-block max-w-full whitespace-pre-wrap wrap-break-word font-mono text-slate-800"
                      title={tc.input.length > 80 ? tc.input : undefined}
                    >
                      Input: {tc.input}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="flex-1 p-6">
            <h3 className="mb-3 text-xs font-semibold uppercase text-slate-500">
              Past Submissions
            </h3>
            {history.length === 0 ? (
              <p className="text-xs text-slate-400">No submissions yet.</p>
            ) : (
              <div className="space-y-2">
                {history.map((s) => (
                  <div key={s.id} className="rounded-lg bg-slate-50 px-3 py-2 text-xs">
                    <div className="flex items-center justify-between">
                      <span className="text-slate-500">
                        {new Date(s.submitted_at).toLocaleString()}
                      </span>
                      <span
                        className={`font-semibold ${s.result === "pass" ? "text-green-600" : "text-red-500"}`}
                      >
                        {s.score}/{s.total}
                      </span>
                    </div>
                    <div className="mt-2 flex flex-wrap gap-2">
                      <button
                        type="button"
                        onClick={() => openSubmissionViewer(s)}
                        disabled={!s.automata_json}
                        className="rounded border border-slate-300 bg-white px-2 py-1 text-[10px] font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-default disabled:opacity-60"
                      >
                        View
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          if (s.automata_json) onLoadSubmission?.(s)
                        }}
                        disabled={!s.automata_json || !onLoadSubmission}
                        className="rounded border border-indigo-300 bg-indigo-50 px-2 py-1 text-[10px] font-medium text-indigo-700 hover:bg-indigo-100 disabled:cursor-default disabled:opacity-60"
                      >
                        Load into canvas
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </aside>

        <main className="flex min-h-0 flex-1 flex-col overflow-hidden p-6">
          <div className="flex min-h-[38vh] max-h-[52vh] shrink-0 flex-col rounded-xl border border-slate-200 bg-white p-2 shadow-sm">
            <div className="min-h-0 flex-1">
              <AutomataCanvas
                key={`${question.id}-${canvasRemountKey}`}
                activeStateId={simHighlight.id}
                alphabet={question.alphabet}
                initialAutomata={automata}
                machine={question.machine}
                simulationStepPulse={simHighlight.pulse}
                onChange={onCanvasChange}
              />
            </div>
          </div>

          <div className="mt-3 flex min-h-0 flex-1 flex-col">
            <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
              <div className="flex shrink-0 gap-1 border-b border-slate-200 bg-slate-50 px-2 pt-2">
                <button
                  type="button"
                  className={tabBtn(resultsTab === "simulation")}
                  onClick={() => setResultsTab("simulation")}
                >
                  Simulation
                </button>
                <button
                  type="button"
                  className={tabBtn(resultsTab === "submission")}
                  onClick={() => setResultsTab("submission")}
                >
                  Submission result
                </button>
              </div>
              <div className="min-h-0 flex-1 overflow-y-auto">
                {resultsTab === "simulation" && (
                  <div className="p-3">
                    <SimulationPanel
                      automata={automata}
                      gradingTests={gradingTests}
                      machine={question.machine}
                      maxLength={question.max_length}
                      practiceUserKey={practiceUserKey ?? null}
                      publicExamples={examples}
                      questionId={question.id}
                      onHighlightState={onSimulationHighlight}
                    />
                  </div>
                )}
                {resultsTab === "submission" && (
                  <div className="p-3">
                    {result ? (
                      <div
                        className={`rounded-xl border font-mono text-xs ${result.result === "pass" ? "border-green-300" : "border-red-300"}`}
                      >
                        <div
                          className={`px-4 py-3 ${result.result === "pass" ? "bg-green-50" : "bg-red-50"}`}
                        >
                          <div className="mb-2 flex items-center gap-3">
                            <span
                              className={`font-sans text-sm font-bold ${result.result === "pass" ? "text-green-700" : "text-red-600"}`}
                            >
                              {result.result === "pass" ? "✓ Passed" : "✗ Failed"}
                            </span>
                            <span className="font-sans text-xs text-slate-500">
                              Score: {result.score} / 20
                            </span>
                          </div>
                          {result.summary.map((line, i) => (
                            <div key={i} className="leading-5 text-slate-700">
                              {line}
                            </div>
                          ))}
                        </div>

                        {result.equiv_lines.length > 0 && (
                          <div className="space-y-0.5 border-t border-slate-200 bg-slate-50 px-4 py-2">
                            <div className="mb-1 font-sans text-[10px] tracking-wide text-slate-400 uppercase">
                              Equivalence Check
                            </div>
                            {result.equiv_lines.map((line, i) => (
                              <div
                                key={i}
                                className={`leading-5 ${
                                  line.startsWith("✓")
                                    ? "font-semibold text-green-700"
                                    : line.startsWith("✗")
                                      ? "font-semibold text-red-600"
                                      : "text-slate-600"
                                }`}
                              >
                                {line}
                              </div>
                            ))}
                          </div>
                        )}

                        <div className="border-t border-slate-200">
                          <div className="bg-white px-4 py-1 font-sans text-[10px] tracking-wide text-slate-400 uppercase">
                            Test Cases ({result.passed}/{result.total} passed)
                          </div>
                          {result.test_details.map((tc, i) => (
                            <div
                              key={`td-${i}-${tc.input.slice(0, 20)}`}
                              className={`flex flex-wrap items-start gap-2 border-t border-slate-100 px-4 py-1 ${tc.correct ? "bg-white" : "bg-red-50"}`}
                            >
                              <span
                                className={`w-8 shrink-0 font-bold ${tc.correct ? "text-green-600" : "text-red-500"}`}
                              >
                                {tc.correct ? "PASS" : "FAIL"}
                              </span>
                              <span className="text-slate-500">|</span>
                              <span
                                className="min-w-0 max-w-full break-all text-slate-800"
                                title={tc.input}
                              >
                                {tc.input}
                              </span>
                              {!tc.correct && (
                                <>
                                  <span className="text-slate-400">|</span>
                                  <span className="min-w-0 text-slate-500">
                                    expected{" "}
                                    <span className="text-slate-700">{tc.expected}</span>{" "}
                                    got{" "}
                                    <span className="text-red-600">{tc.got}</span>
                                  </span>
                                  <span className="text-slate-400">|</span>
                                  <span className="min-w-0 max-w-full wrap-break-word text-slate-500 italic">
                                    {tc.reason}
                                  </span>
                                </>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    ) : (
                      <p className="text-sm text-slate-500">
                        Submit your diagram to see grading, score, and per-test
                        feedback here.
                      </p>
                    )}
                  </div>
                )}
              </div>
            </div>

            <div className="mt-3 flex shrink-0 flex-wrap items-center gap-4 border-t border-slate-200 bg-white pt-3">
              <button
                onClick={onSubmit}
                disabled={submitting}
                className="rounded-lg bg-blue-600 px-6 py-2 text-sm font-semibold text-white transition hover:bg-blue-700 disabled:opacity-50"
              >
                {submitting ? "Grading…" : "Submit"}
              </button>
              {showPrevButton && (
                <button
                  type="button"
                  onClick={onPreviousQuestion}
                  className="rounded-lg border border-slate-300 bg-white px-5 py-2 text-sm font-medium text-slate-800 hover:bg-slate-50"
                >
                  Previous question
                </button>
              )}
              {showNextButton && (
                <button
                  type="button"
                  onClick={onNextQuestion}
                  className="rounded-lg border border-slate-300 bg-white px-5 py-2 text-sm font-medium text-slate-800 hover:bg-slate-50"
                >
                  Next question
                </button>
              )}
              {error && <p className="text-sm text-red-500">{error}</p>}
            </div>
          </div>
        </main>
      </div>

    </div>
  )
}
