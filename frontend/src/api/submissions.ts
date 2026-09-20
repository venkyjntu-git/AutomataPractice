export interface AutomataTransition {
  from_state: string
  to_state: string
  symbol: string // input symbol (DFA/NFA/PDA) or read symbol (TM)
  // PDA only
  stack_top?: string // symbol expected on top of stack (ε = any)
  stack_push?: string // symbols pushed after pop (ε = pop only)
  // TM only
  write?: string // symbol to write
  direction?: string // 'L' | 'R'
}

export interface AutomataPayload {
  states: { id: string; label?: string; initial: boolean; accept: boolean }[]
  transitions: AutomataTransition[]
}

export interface TestCaseResult {
  input: string
  expected: string
  got: string
  correct: boolean
  reason: string
}

export interface SubmissionResult {
  result: "pass" | "fail"
  score: number // 0–20
  passed: number
  total: number
  summary: string[] // header lines
  equiv_lines: string[] // equivalence section
  test_details: TestCaseResult[]
}

export interface PastSubmission {
  id: number
  submitted_at: string
  result: string
  score: number
  total: number
  automata_json?: AutomataPayload
}

export interface SimStep {
  kind: string
  state?: string | null
  remaining_input?: string | null
  active_states?: string[] | null
  stack?: string[] | null
  tape?: string[] | null
  head?: number | null
  note: string
}

export interface SingleSimResult {
  machine: string
  input: string
  expected?: string | null
  got: string
  correct?: boolean | null
  accepted: boolean
  final_reason: string
  steps: SimStep[]
}

export interface SimulateOut {
  runs: SingleSimResult[]
}

export interface SimulateRequestBody {
  automata: AutomataPayload
  mode: "custom_input" | "test_suite" | "single_test"
  input?: string
  suite?: "public" | "private" | "all"
  test_index?: number
}
