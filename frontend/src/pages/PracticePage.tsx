/// <reference types="vite/client" />
/// <reference types="vite-plugin-svgr/client" />

import axios from "axios"
import {
  ensurePracticeUserKey,
  generatePracticeQuestion,
  getPracticeHistory,
  type DifficultyTier,
  type PracticeHistoryRow,
  type QuestionStyle,
} from "@/api/practice"
import DFA from "@/assets/DFA.svg?react"
import PDA from "@/assets/PDA.svg?react"
import TM from "@/assets/TM.svg?react"
import { Card, CardContent, CardTitle } from "@/components/ui/card"
import { useEffect, useState } from "react"
import { useNavigate } from "react-router-dom"

type Machine = "DFA" | "PDA" | "TM"

const DIFFICULTY_OPTIONS = ["0", "1", "2", "3", "4", "5"]

const STYLE_OPTIONS: { value: QuestionStyle; label: string }[] = [
  { value: "random", label: "Random (mix)" },
  { value: "simple", label: "Simple (no closure ops)" },
  { value: "closure", label: "Closure only" },
]

const TIER_OPTIONS: { value: DifficultyTier; label: string }[] = [
  { value: "any", label: "Any" },
  { value: "easy", label: "Easy" },
  { value: "medium", label: "Medium" },
  { value: "hard", label: "Hard" },
]

function detailFromAxios(e: unknown): string | undefined {
  if (axios.isAxiosError(e)) {
    const d = e.response?.data as { detail?: string | string[] } | undefined
    if (Array.isArray(d?.detail)) return d.detail.map(String).join("; ")
    if (typeof d?.detail === "string") return d.detail
  }
  return undefined
}

export default function PracticePage() {
  const navigate = useNavigate()
  const [bootError, setBootError] = useState("")
  const [generating, setGenerating] = useState(false)
  const [machine, setMachine] = useState<Machine | null>(null)
  const [questionStyle, setQuestionStyle] = useState<QuestionStyle>("simple")
  const [difficultyTier, setDifficultyTier] = useState<DifficultyTier>("any")
  const [difficulty, setDifficulty] = useState<string>("")
  const [historyOpen, setHistoryOpen] = useState(false)
  const [historyRows, setHistoryRows] = useState<PracticeHistoryRow[]>([])
  const [historyLoading, setHistoryLoading] = useState(false)
  const [historyError, setHistoryError] = useState("")

  useEffect(() => {
    ensurePracticeUserKey().catch(() =>
      setBootError("Could not start a practice session. Is the API running?")
    )
  }, [])

  async function openHistory() {
    setHistoryOpen(true)
    setHistoryLoading(true)
    setHistoryError("")
    try {
      const key = await ensurePracticeUserKey()
      const rows = await getPracticeHistory(key)
      setHistoryRows(rows)
    } catch (e) {
      setHistoryRows([])
      setHistoryError(detailFromAxios(e) ?? "Could not load history.")
    } finally {
      setHistoryLoading(false)
    }
  }

  async function onGenerate() {
    if (!machine || generating) return
    setBootError("")
    setGenerating(true)
    try {
      const key = await ensurePracticeUserKey()
      const qid = await generatePracticeQuestion(machine, key, {
        question_style: questionStyle,
        difficulty_tier: difficultyTier,
        difficulty: difficultyTier === "any" ? difficulty || undefined : undefined,
      })
      if (historyOpen) {
        void (async () => {
          try {
            const rows = await getPracticeHistory(key)
            setHistoryRows(rows)
          } catch {
            /* ignore background refresh */
          }
        })()
      }
      navigate(`/practice/question/${qid}`, { state: { practiceNavReset: true } })
    } catch (e) {
      setBootError(
        detailFromAxios(e) ??
          "Failed to generate a question. Try different options or try again."
      )
    } finally {
      setGenerating(false)
    }
  }

  return (
    <div className="flex min-h-screen flex-col items-center bg-gradient-to-b from-slate-100 via-slate-50 to-white px-4 py-10 sm:py-14">
      <div className="mb-8 flex w-full max-w-xl flex-col items-center gap-3 text-center">
        <div className="flex w-full items-center justify-between gap-4">
          <h1 className="text-xl font-semibold tracking-tight text-slate-900 sm:text-2xl">
            Practice
          </h1>
          <button
            type="button"
            onClick={() => void openHistory()}
            className="rounded-full border border-slate-200 bg-white px-4 py-2 text-xs font-medium text-slate-700 shadow-sm transition hover:border-slate-300 hover:bg-slate-50"
          >
            History
          </button>
        </div>
        <p className="max-w-md text-sm leading-relaxed text-slate-600">
          {machine
            ? "Choose question style, difficulty tier, then generate a fresh problem."
            : "Pick a machine type to get started."}
        </p>
      </div>
      {bootError && (
        <p
          className="mb-6 max-w-xl rounded-lg border border-red-100 bg-red-50 px-4 py-3 text-center text-sm text-red-700"
          role="alert"
        >
          {bootError}
        </p>
      )}

      {!machine ? (
        <div className="flex flex-wrap items-center justify-center gap-8">
          {(
            [
              ["DFA", DFA],
              ["PDA", PDA],
              ["TM", TM],
            ] as const
          ).map(([m, Icon]) => (
            <button
              key={m}
              type="button"
              onClick={() => setMachine(m as Machine)}
              className="rounded-xl border border-transparent p-0 transition hover:border-slate-200 hover:shadow-md"
            >
              <Card className="items-center">
                <CardTitle>{m === "TM" ? "Turing Machine" : m}</CardTitle>
                <CardContent>
                  <Icon />
                </CardContent>
              </Card>
            </button>
          ))}
        </div>
      ) : (
        <div className="w-full max-w-md rounded-2xl border border-slate-200/80 bg-white/90 p-6 shadow-md shadow-slate-200/50 backdrop-blur-sm sm:p-8">
          <p className="mb-5 text-center text-sm font-medium text-slate-700">
            Machine:{" "}
            <span className="rounded-full bg-slate-100 px-3 py-1 font-mono text-xs">
              {machine}
            </span>
          </p>

          <p className="mb-2 text-xs font-medium text-slate-600">Question style</p>
          <div className="mb-4 flex flex-col gap-2">
            {STYLE_OPTIONS.map(({ value, label }) => (
              <label
                key={value}
                className="flex cursor-pointer items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm hover:bg-slate-50"
              >
                <input
                  type="radio"
                  name="qstyle"
                  checked={questionStyle === value}
                  onChange={() => setQuestionStyle(value)}
                  className="border-slate-300"
                />
                {label}
              </label>
            ))}
          </div>

          <label className="mb-2 block text-xs font-medium text-slate-600">
            Difficulty tier
          </label>
          <select
            className="mb-4 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            value={difficultyTier}
            onChange={(e) => setDifficultyTier(e.target.value as DifficultyTier)}
          >
            {TIER_OPTIONS.map(({ value, label }) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>

          {difficultyTier === "any" && (
            <>
              <label className="mb-2 block text-xs font-medium text-slate-600">
                Template difficulty (optional, 0–5)
              </label>
              <select
                className="mb-4 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                value={difficulty}
                onChange={(e) => setDifficulty(e.target.value)}
              >
                <option value="">Any</option>
                {DIFFICULTY_OPTIONS.map((d) => (
                  <option key={d} value={d}>
                    {d}
                  </option>
                ))}
              </select>
            </>
          )}

          <div className="mt-6 flex flex-wrap gap-3">
            <button
              type="button"
              onClick={() => {
                setMachine(null)
                setQuestionStyle("simple")
                setDifficultyTier("any")
                setDifficulty("")
              }}
              className="rounded-lg border border-slate-300 px-4 py-2 text-sm text-slate-700 hover:bg-slate-50"
            >
              ← Change machine
            </button>
            <button
              type="button"
              disabled={generating}
              onClick={() => void onGenerate()}
              className="rounded-lg bg-blue-600 px-5 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {generating ? "Generating…" : "Generate"}
            </button>
          </div>
        </div>
      )}

      {historyOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/45 p-4 backdrop-blur-[2px]"
          role="dialog"
          aria-modal="true"
        >
          <div className="flex max-h-[min(85vh,720px)] w-full max-w-lg flex-col overflow-hidden rounded-2xl bg-white shadow-2xl ring-1 ring-slate-200/60">
            <div className="flex shrink-0 items-center justify-between border-b border-slate-100 px-5 py-4">
              <h2 className="text-base font-semibold text-slate-900">Question history</h2>
              <button
                type="button"
                onClick={() => setHistoryOpen(false)}
                className="rounded-lg p-1.5 text-slate-500 transition hover:bg-slate-100 hover:text-slate-800"
                aria-label="Close"
              >
                ✕
              </button>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-5 py-4">
              {historyError && (
                <p className="mb-3 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700" role="alert">
                  {historyError}
                </p>
              )}
              {historyLoading ? (
                <p className="text-sm text-slate-500">Loading…</p>
              ) : historyRows.length === 0 && !historyError ? (
                <p className="text-sm text-slate-500">No questions in this session yet.</p>
              ) : (
                <ul className="space-y-2 pr-1">
                  {historyRows.map((r) => (
                    <li key={r.id}>
                      <button
                        type="button"
                        onClick={() => {
                          setHistoryOpen(false)
                          navigate(`/practice/question/${r.id}`, {
                            state: { practiceNavReset: true },
                          })
                        }}
                        className="w-full rounded-xl border border-slate-100 bg-slate-50/80 px-4 py-3 text-left text-sm transition hover:border-slate-200 hover:bg-white"
                      >
                        <span className="font-mono text-xs text-slate-500">#{r.id}</span>{" "}
                        <span className="font-medium text-slate-800">{r.machine}</span>
                        {r.difficulty != null && r.difficulty !== "" && (
                          <span className="text-slate-400"> · diff {r.difficulty}</span>
                        )}
                        {r.is_closure && (
                          <span className="ml-1 text-xs font-medium text-amber-700">closure</span>
                        )}
                        <span className="mt-1 block text-xs text-slate-500">
                          {new Date(r.generated_at).toLocaleString()}
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
