/**
 * TransitionDialog — modal for entering/editing transition labels.
 *
 * Renders machine-specific fields:
 *   DFA / NFA  : Symbol
 *   PDA        : Symbol  |  Stack Top (pop)  |  Stack Push
 *   TM         : Read    |  Write            |  Direction (L/R)
 *
 * The dialog is centered on screen.
 * Enter = confirm, Escape = cancel.
 */
import { useEffect, useRef, useState } from 'react'

export interface TransitionFields {
  symbol:      string
  stack_top?:  string   // PDA
  stack_push?: string   // PDA
  write?:      string   // TM
  direction?:  string   // TM
}

interface Props {
  machine:     string
  initial?:    TransitionFields   // pre-filled when editing an existing transition
  onConfirm:   (fields: TransitionFields) => void
  onCancel:    () => void
}

export default function TransitionDialog({ machine, initial, onConfirm, onCancel }: Props) {
  const [symbol,    setSymbol]    = useState(initial?.symbol    ?? 'ε')
  const [stackTop,  setStackTop]  = useState(initial?.stack_top  ?? 'ε')
  const [stackPush, setStackPush] = useState(initial?.stack_push ?? 'ε')
  const [write,     setWrite]     = useState(initial?.write      ?? 'ε')
  const [direction, setDirection] = useState<'L' | 'R'>((initial?.direction as 'L' | 'R') ?? 'R')

  const firstRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    firstRef.current?.focus()
    firstRef.current?.select()
  }, [])

  function confirm() {
    const sym = symbol.trim() || 'ε'
    if (machine === 'PDA') {
      onConfirm({ symbol: sym, stack_top: stackTop.trim() || 'ε', stack_push: stackPush.trim() || 'ε' })
    } else if (machine === 'TM') {
      onConfirm({ symbol: sym, write: write.trim() || 'ε', direction })
    } else {
      onConfirm({ symbol: sym })
    }
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter')  { e.preventDefault(); confirm() }
    if (e.key === 'Escape') { e.preventDefault(); onCancel() }
  }

  const isPda = machine === 'PDA'
  const isTm  = machine === 'TM'

  return (
    /* Backdrop */
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ background: 'rgba(0,0,0,0.25)' }}
      onClick={(e) => { if (e.target === e.currentTarget) onCancel() }}
    >
      <div
        className="bg-white rounded-xl shadow-2xl border border-slate-200 p-5 w-72"
        onKeyDown={handleKeyDown}
      >
        <h3 className="text-sm font-semibold text-slate-700 mb-4">
          {initial ? 'Edit Transition' : 'Add Transition'}
        </h3>

        <div className="space-y-3">
          {/* Symbol / Read */}
          <Field
            label={isTm ? 'Read' : 'Symbol'}
            hint={isTm ? 'Symbol to read from tape' : 'ε for epsilon'}
            value={symbol}
            onChange={setSymbol}
            inputRef={firstRef}
          />

          {/* PDA: Stack Top + Push */}
          {isPda && (
            <>
              <Field
                label="Stack Top"
                hint="Symbol to pop (ε = any)"
                value={stackTop}
                onChange={setStackTop}
              />
              <Field
                label="Stack Push"
                hint="Symbols to push (ε = pop only)"
                value={stackPush}
                onChange={setStackPush}
              />
            </>
          )}

          {/* TM: Write + Direction */}
          {isTm && (
            <>
              <Field
                label="Write"
                hint="Symbol to write to tape"
                value={write}
                onChange={setWrite}
              />
              <div className="flex items-center gap-3">
                <span className="text-xs text-slate-500 w-20 shrink-0">Direction</span>
                <div className="flex gap-2">
                  {(['L', 'R'] as const).map((d) => (
                    <button
                      key={d}
                      type="button"
                      onClick={() => setDirection(d)}
                      className={[
                        'px-3 py-1 rounded text-xs font-semibold border transition',
                        direction === d
                          ? 'bg-blue-600 border-blue-600 text-white'
                          : 'border-slate-300 text-slate-600 hover:bg-slate-50',
                      ].join(' ')}
                    >
                      {d === 'L' ? '← L' : 'R →'}
                    </button>
                  ))}
                </div>
              </div>
            </>
          )}
        </div>

        {/* Buttons */}
        <div className="flex justify-end gap-2 mt-5">
          <button
            onClick={onCancel}
            className="px-3 py-1.5 text-xs text-slate-500 hover:bg-slate-100 rounded-lg transition"
          >
            Cancel
          </button>
          <button
            onClick={confirm}
            className="px-4 py-1.5 text-xs font-semibold bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition"
          >
            OK
          </button>
        </div>
      </div>
    </div>
  )
}

interface FieldProps {
  label:    string
  hint?:    string
  value:    string
  onChange: (v: string) => void
  inputRef?: React.RefObject<HTMLInputElement | null>
}
function Field({ label, hint, value, onChange, inputRef }: FieldProps) {
  return (
    <div className="flex items-center gap-3">
      <span className="text-xs text-slate-500 w-20 shrink-0">{label}</span>
      <div className="flex-1">
        <input
          ref={inputRef}
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={hint}
          className="w-full border border-slate-300 rounded-lg px-2.5 py-1.5 text-xs font-mono
                     focus:outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-200"
        />
      </div>
    </div>
  )
}
