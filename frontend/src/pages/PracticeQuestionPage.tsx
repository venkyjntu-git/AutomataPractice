/**
 * Practice question view — same layout as student QuestionPage, but uses
 * anonymous practice_user_key from localStorage (no login).
 */
import {
  canPracticeNavigateBack,
  ensurePracticeUserKey,
  generatePracticeQuestion,
  getPracticeNavStack,
  getPracticeQuestion,
  getPracticeSubmissions,
  loadPracticePrefs,
  popPracticeNavToPrevious,
  pushPracticeNavAfter,
  resetPracticeNavStack,
  submitPracticeAutomata,
} from "@/api/practice"
import type { Question } from "@/api/questions"
import type {
  AutomataPayload,
  PastSubmission,
  SubmissionResult,
} from "@/api/submissions"

import QuestionAnswerComponent from "@/components/QuestionAnswerComponent"
import { useCallback, useEffect, useState } from "react"
import { useLocation, useNavigate, useParams } from "react-router-dom"

export default function PracticeQuestionPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const location = useLocation()
  const qid = Number(id)

  const [practiceKey, setPracticeKey] = useState<string | null>(null)
  const [question, setQuestion] = useState<Question | null>(null)
  const [automata, setAutomata] = useState<AutomataPayload>({
    states: [],
    transitions: [],
  })
  const [result, setResult] = useState<SubmissionResult | null>(null)
  const [history, setHistory] = useState<PastSubmission[]>([])
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState("")
  const [canvasRemountKey, setCanvasRemountKey] = useState(0)

  useEffect(() => {
    const st = location.state as { practiceNavReset?: boolean } | undefined
    if (st?.practiceNavReset) {
      resetPracticeNavStack(qid)
      navigate(`/practice/question/${qid}`, { replace: true })
      return
    }
    const s = getPracticeNavStack()
    if (s.length === 0) {
      resetPracticeNavStack(qid)
    }
  }, [qid, navigate, location.state])

  useEffect(() => {
    let cancelled = false
    setResult(null)
    setAutomata({ states: [], transitions: [] })
    ;(async () => {
      const key = await ensurePracticeUserKey()
      if (cancelled) return
      setPracticeKey(key)
      try {
        const q = await getPracticeQuestion(qid, key)
        if (cancelled) return
        setQuestion(q)
      } catch {
        navigate("/practice")
        return
      }
      try {
        const h = await getPracticeSubmissions(qid, key)
        if (!cancelled) setHistory(h)
      } catch {
        /* ignore */
      }
    })()
    return () => {
      cancelled = true
    }
  }, [qid, navigate])

  const handleCanvasChange = useCallback((a: AutomataPayload) => {
    setAutomata(a)
  }, [])

  const handleLoadSubmission = useCallback((s: PastSubmission) => {
    if (!s.automata_json) return
    setAutomata(s.automata_json)
    setCanvasRemountKey((k) => k + 1)
    setError("")
  }, [])

  async function handleSubmit() {
    if (!practiceKey) return
    if (automata.states.length === 0) {
      setError("Draw at least one state before submitting.")
      return
    }
    setError("")
    setSubmitting(true)
    try {
      const res = await submitPracticeAutomata(qid, practiceKey, automata)
      setResult(res)
      const h = await getPracticeSubmissions(qid, practiceKey)
      setHistory(h)
    } catch {
      setError("Submission failed. Please try again.")
    } finally {
      setSubmitting(false)
    }
  }

  async function handleNextQuestion() {
    if (!practiceKey) return
    setResult(null)
    setError("")
    const prefs = loadPracticePrefs()
    const machine = prefs?.machine ?? question?.machine ?? "DFA"
    try {
      const newId = await generatePracticeQuestion(machine, practiceKey, {
        question_style: prefs?.question_style,
        difficulty_tier: prefs?.difficulty_tier,
        difficulty: prefs?.difficulty || undefined,
      })
      pushPracticeNavAfter(qid, newId)
      navigate(`/practice/question/${newId}`)
    } catch {
      setError("Could not start the next question. Check options on the Practice page.")
    }
  }

  function handlePreviousQuestion() {
    const prev = popPracticeNavToPrevious()
    if (prev == null) return
    setResult(null)
    setError("")
    navigate(`/practice/question/${prev}`)
  }

  return (
    <QuestionAnswerComponent
      allowNextWithoutSubmit
      automata={automata}
      canvasRemountKey={canvasRemountKey}
      error={error}
      history={history}
      nextRequiresResult
      onBack={() => navigate("/practice")}
      onNextQuestion={handleNextQuestion}
      onPreviousQuestion={handlePreviousQuestion}
      practiceUserKey={practiceKey}
      onSubmit={handleSubmit}
      question={question}
      result={result}
      showNextNav={true}
      showPrevNav={canPracticeNavigateBack()}
      submitting={submitting}
      onCanvasChange={handleCanvasChange}
      onLoadSubmission={handleLoadSubmission}
    />
  )
}
