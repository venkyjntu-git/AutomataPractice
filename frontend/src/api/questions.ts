export interface Question {
  id: number
  machine: string
  difficulty: string | null
  text: string
  alphabet: string[]
  max_length: number
  is_closure: boolean
  template_id: string | null
  /** Safe example strings shown before submit (not full grading set). */
  public_examples?: TestCase[]
  /** Full private grading suite (same as server test_cases) for simulation UI. */
  grading_tests?: TestCase[]
}

export interface TestCase {
  input: string
  label: string
}
