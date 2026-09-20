import client from "@/api/client"
import type {
  AutomataPayload,
  PastSubmission,
  SimulateOut,
  SimulateRequestBody,
  SubmissionResult,
} from "@/api/submissions"
import type { Question } from "@/api/questions"

const PRACTICE_KEY = "practice_user_key"
export const PRACTICE_PREFS_KEY = "practice_generate_prefs"
const PRACTICE_NAV_STACK = "practice_question_nav_stack"

export function getPracticeNavStack(): number[] {
  try {
    const raw = sessionStorage.getItem(PRACTICE_NAV_STACK)
    if (!raw) return []
    const parsed = JSON.parse(raw) as unknown
    if (!Array.isArray(parsed)) return []
    return parsed.map(Number).filter((n) => Number.isFinite(n))
  } catch {
    return []
  }
}

export function resetPracticeNavStack(questionId: number): void {
  sessionStorage.setItem(PRACTICE_NAV_STACK, JSON.stringify([questionId]))
}

/** Append after generating a new question while on `fromQuestionId`. */
export function pushPracticeNavAfter(fromQuestionId: number, newQuestionId: number): void {
  const s = getPracticeNavStack()
  let next: number[]
  if (s.length === 0) {
    next = [fromQuestionId, newQuestionId]
  } else if (s[s.length - 1] === fromQuestionId) {
    next = [...s, newQuestionId]
  } else {
    next = [fromQuestionId, newQuestionId]
  }
  sessionStorage.setItem(PRACTICE_NAV_STACK, JSON.stringify(next))
}

/** Pop current question id and return the previous id, or null if none. */
export function popPracticeNavToPrevious(): number | null {
  const s = getPracticeNavStack()
  if (s.length <= 1) return null
  s.pop()
  sessionStorage.setItem(PRACTICE_NAV_STACK, JSON.stringify(s))
  return s[s.length - 1] ?? null
}

export function canPracticeNavigateBack(): boolean {
  return getPracticeNavStack().length > 1
}

export type QuestionStyle = "random" | "simple" | "closure"
export type DifficultyTier = "easy" | "medium" | "hard" | "any"

export interface PracticeGeneratePrefs {
  machine: string
  question_style: QuestionStyle
  difficulty_tier: DifficultyTier
  /** When difficulty_tier is "any", optional legacy 0–5 filter */
  difficulty: string
}

export function getStoredPracticeUserKey(): string | null {
  return localStorage.getItem(PRACTICE_KEY)
}

export async function ensurePracticeUserKey(): Promise<string> {
  const existing = localStorage.getItem(PRACTICE_KEY)
  if (existing) return existing
  const { data } = await client.post<{ practice_user_key: string }>("/practice/session")
  localStorage.setItem(PRACTICE_KEY, data.practice_user_key)
  return data.practice_user_key
}

export function savePracticePrefs(p: PracticeGeneratePrefs): void {
  try {
    sessionStorage.setItem(PRACTICE_PREFS_KEY, JSON.stringify(p))
  } catch {
    /* ignore */
  }
}

function migrateLegacyPrefs(raw: Record<string, unknown>): PracticeGeneratePrefs {
  const machine = typeof raw.machine === "string" ? raw.machine : "DFA"
  const closureOnly = Boolean(raw.closure_only)
  const difficulty = typeof raw.difficulty === "string" ? raw.difficulty : ""
  let question_style: QuestionStyle = closureOnly ? "closure" : "simple"
  if (raw.question_style === "random" || raw.question_style === "simple" || raw.question_style === "closure") {
    question_style = raw.question_style
  }
  let difficulty_tier: DifficultyTier = "any"
  if (
    raw.difficulty_tier === "easy" ||
    raw.difficulty_tier === "medium" ||
    raw.difficulty_tier === "hard" ||
    raw.difficulty_tier === "any"
  ) {
    difficulty_tier = raw.difficulty_tier
  }
  return { machine, question_style, difficulty_tier, difficulty }
}

export function loadPracticePrefs(): PracticeGeneratePrefs | null {
  try {
    const raw = sessionStorage.getItem(PRACTICE_PREFS_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as Record<string, unknown>
    return migrateLegacyPrefs(parsed)
  } catch {
    return null
  }
}

export async function generatePracticeQuestion(
  machine: string,
  practiceUserKey: string,
  opts?: {
    question_style?: QuestionStyle
    difficulty_tier?: DifficultyTier
    difficulty?: string
  }
): Promise<number> {
  const question_style = opts?.question_style ?? "simple"
  const difficulty_tier = opts?.difficulty_tier ?? "any"
  const body: Record<string, unknown> = {
    practice_user_key: practiceUserKey,
    machine,
    question_style,
    difficulty_tier,
  }
  if (difficulty_tier === "any" && opts?.difficulty !== undefined && opts.difficulty !== "") {
    body.difficulty = opts.difficulty
  }
  const { data } = await client.post<{ question_id: number }>("/practice/generate", body)
  savePracticePrefs({
    machine,
    question_style,
    difficulty_tier,
    difficulty: difficulty_tier === "any" ? (opts?.difficulty ?? "") : "",
  })
  return data.question_id
}

export async function getPracticeQuestion(
  questionId: number,
  practiceUserKey: string
): Promise<Question> {
  const { data } = await client.get<Question>(`/practice/question/${questionId}`, {
    params: { practice_user_key: practiceUserKey },
  })
  return data
}

export interface PracticeHistoryRow {
  id: number
  machine: string
  difficulty: string | null
  is_closure: boolean
  generated_at: string
}

export async function getPracticeHistory(
  practiceUserKey: string
): Promise<PracticeHistoryRow[]> {
  const { data } = await client.get<PracticeHistoryRow[]>("/practice/history", {
    params: { practice_user_key: practiceUserKey },
  })
  return data
}

export async function submitPracticeAutomata(
  questionId: number,
  practiceUserKey: string,
  automata: AutomataPayload
): Promise<SubmissionResult> {
  const { data } = await client.post<SubmissionResult>(
    `/practice/submit/${questionId}`,
    automata,
    { params: { practice_user_key: practiceUserKey } }
  )
  return data
}

export async function getPracticeSubmissions(
  questionId: number,
  practiceUserKey: string
): Promise<PastSubmission[]> {
  const { data } = await client.get<PastSubmission[]>(
    `/practice/submissions/${questionId}`,
    { params: { practice_user_key: practiceUserKey } }
  )
  return data
}

export async function simulatePracticeAutomata(
  questionId: number,
  practiceUserKey: string,
  body: SimulateRequestBody
): Promise<SimulateOut> {
  const { data } = await client.post<SimulateOut>(
    `/practice/simulate/${questionId}`,
    body,
    { params: { practice_user_key: practiceUserKey } }
  )
  return data
}
