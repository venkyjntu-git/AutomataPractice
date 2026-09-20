import type { AutomataPayload } from "@/api/submissions"

export interface AutomataViewerSnapshot {
  title: string
  machine: string
  alphabet: string[]
  automata: AutomataPayload | null
  createdAt: number
}

const PREFIX = "automata_viewer_snapshot:"

export function createAutomataViewerSnapshot(
  input: Omit<AutomataViewerSnapshot, "createdAt">
): string {
  const token = `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
  const payload: AutomataViewerSnapshot = {
    ...input,
    createdAt: Date.now(),
  }
  sessionStorage.setItem(`${PREFIX}${token}`, JSON.stringify(payload))
  return token
}

export function getAutomataViewerSnapshot(token: string): AutomataViewerSnapshot | null {
  const raw = sessionStorage.getItem(`${PREFIX}${token}`)
  if (!raw) return null
  try {
    return JSON.parse(raw) as AutomataViewerSnapshot
  } catch {
    return null
  }
}
