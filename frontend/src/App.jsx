import { useEffect, useRef, useState } from 'react'
import ApprovalCard from './components/ApprovalCard.jsx'
import Markdown from './components/Markdown.jsx'
import ReportsPanel from './components/ReportsPanel.jsx'
import ToolStep from './components/ToolStep.jsx'

/*
 * One "turn" = { user, recalled: [], items: [step|approval...], answer, error }
 * where a step is  { kind:'step', name, args, result, pending, declined }
 * and an approval  { kind:'approval', name, args, status }
 * Ordered `items` keeps the trace in the exact order the agent produced it.
 */

export default function App() {
  const [connected, setConnected] = useState(false)
  const [memoryFacts, setMemoryFacts] = useState([])
  const [showMemory, setShowMemory] = useState(false)
  const [showReports, setShowReports] = useState(false)
  const [turns, setTurns] = useState([])
  const [busy, setBusy] = useState(false)
  const [input, setInput] = useState('')
  const wsRef = useRef(null)
  const bottomRef = useRef(null)

  const patchLastTurn = (fn) =>
    setTurns((prev) => {
      if (prev.length === 0) return prev
      const next = [...prev]
      next[next.length - 1] = fn(structuredClone(next[next.length - 1]))
      return next
    })

  useEffect(() => {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws'
    const ws = new WebSocket(`${proto}://${location.host}/ws`)
    wsRef.current = ws

    ws.onopen = () => setConnected(true)
    ws.onclose = () => setConnected(false)
    ws.onmessage = (e) => {
      const event = JSON.parse(e.data)
      switch (event.type) {
        case 'memory_loaded':
          setMemoryFacts(event.facts)
          break
        case 'memory_recalled':
          patchLastTurn((t) => ({ ...t, recalled: event.facts }))
          break
        case 'tool_call':
          patchLastTurn((t) => ({
            ...t,
            items: [...t.items, { kind: 'step', name: event.name, args: event.args, pending: true }],
          }))
          break
        case 'approval_request':
          patchLastTurn((t) => ({
            ...t,
            items: [...t.items, { kind: 'approval', name: event.name, args: event.args, status: 'pending' }],
          }))
          break
        case 'tool_result':
          patchLastTurn((t) => {
            for (let i = t.items.length - 1; i >= 0; i--) {
              const it = t.items[i]
              if (it.kind === 'step' && it.name === event.name && it.pending) {
                t.items[i] = { ...it, pending: false, result: event.result, declined: !!event.declined }
                break
              }
            }
            return t
          })
          break
        case 'final':
          patchLastTurn((t) => ({ ...t, answer: event.content }))
          setBusy(false)
          break
        case 'error':
          patchLastTurn((t) => ({ ...t, error: event.message }))
          setBusy(false)
          break
        default:
          break // 'retry' etc. — not shown in the UI
      }
    }
    return () => ws.close()
  }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [turns, busy])

  const send = () => {
    const text = input.trim()
    if (!text || busy || !connected) return
    setTurns((prev) => [...prev, { user: text, recalled: [], items: [] }])
    setBusy(true)
    setInput('')
    wsRef.current.send(JSON.stringify({ type: 'user_message', content: text }))
  }

  const decide = (approved) => {
    wsRef.current.send(JSON.stringify({ type: 'approval_response', approved }))
    patchLastTurn((t) => {
      for (let i = t.items.length - 1; i >= 0; i--) {
        if (t.items[i].kind === 'approval' && t.items[i].status === 'pending') {
          t.items[i] = { ...t.items[i], status: approved ? 'approved' : 'rejected' }
          break
        }
      }
      return t
    })
  }

  return (
    <div className="h-screen flex flex-col bg-zinc-950 text-zinc-100">
      <header className="border-b border-zinc-800 px-4 py-3">
        <div className="max-w-3xl mx-auto flex items-center gap-3">
          <h1 className="text-sm font-semibold tracking-wide">
            🤖 Agent Lab <span className="text-zinc-500 font-normal">— reasoning made visible</span>
          </h1>
          <span
            className={`size-2 rounded-full ${connected ? 'bg-emerald-400' : 'bg-red-500'}`}
            title={connected ? 'connected' : 'disconnected'}
          />
          <div className="ml-auto flex items-center gap-2">
            {memoryFacts.length > 0 && (
              <button
                onClick={() => setShowMemory(!showMemory)}
                className="px-2.5 py-1 rounded-full bg-violet-500/15 border border-violet-500/40 text-violet-300 text-xs cursor-pointer"
              >
                🧠 {memoryFacts.length} memor{memoryFacts.length === 1 ? 'y' : 'ies'}
              </button>
            )}
            <button
              onClick={() => setShowReports(true)}
              className="px-2.5 py-1 rounded-full bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-xs cursor-pointer"
            >
              📄 Reports
            </button>
          </div>
        </div>
        {showMemory && (
          <div className="max-w-3xl mx-auto mt-2 rounded-lg border border-violet-500/30 bg-violet-500/5 px-3 py-2 text-xs text-violet-200">
            <div className="font-medium mb-1">Loaded from long-term memory:</div>
            <ul className="list-disc ml-4 space-y-0.5">
              {memoryFacts.map((f, i) => (
                <li key={i}>{f}</li>
              ))}
            </ul>
          </div>
        )}
      </header>

      <main className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto px-4 py-6 space-y-8">
          {turns.length === 0 && (
            <div className="text-center text-zinc-500 text-sm mt-16 space-y-2">
              <p className="text-3xl">🛠️</p>
              <p>Ask anything. Tool calls, code approvals and memory all show up right here.</p>
              <p className="text-xs">
                Try: “What is 847 × 23?” · “Research the latest trends in health data analytics” ·
                “Write python to sort a list of dates”
              </p>
            </div>
          )}

          {turns.map((turn, i) => (
            <div key={i} className="space-y-3">
              <div className="flex justify-end">
                <div className="max-w-[85%] rounded-2xl rounded-br-sm bg-sky-600/90 px-4 py-2 text-sm whitespace-pre-wrap">
                  {turn.user}
                </div>
              </div>

              {turn.recalled.length > 0 && (
                <div className="text-xs text-violet-300/90">
                  🧠 recalled: {turn.recalled.join(' · ')}
                </div>
              )}

              {turn.items.length > 0 && (
                <div className="space-y-2">
                  {turn.items.map((item, j) =>
                    item.kind === 'approval' ? (
                      <ApprovalCard key={j} approval={item} onDecide={decide} />
                    ) : (
                      <ToolStep key={j} step={item} />
                    )
                  )}
                </div>
              )}

              {turn.answer && (
                <div className="pt-1">
                  <Markdown>{turn.answer}</Markdown>
                </div>
              )}
              {turn.error && (
                <div className="rounded-lg border border-red-500/40 bg-red-500/10 px-3 py-2 text-sm text-red-300">
                  {turn.error}
                </div>
              )}
              {!turn.answer && !turn.error && i === turns.length - 1 && busy && (
                <div className="flex items-center gap-2 text-sm text-zinc-500">
                  <span className="inline-block size-3.5 rounded-full border-2 border-zinc-700 border-t-zinc-400 animate-spin" />
                  thinking…
                </div>
              )}
            </div>
          ))}
          <div ref={bottomRef} />
        </div>
      </main>

      <footer className="border-t border-zinc-800 p-3">
        <div className="max-w-3xl mx-auto flex gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                send()
              }
            }}
            rows={1}
            placeholder={connected ? 'Message the agent…' : 'Connecting…'}
            className="flex-1 resize-none rounded-xl bg-zinc-900 border border-zinc-800 focus:border-zinc-600 focus:outline-none px-4 py-2.5 text-sm placeholder-zinc-600"
          />
          <button
            onClick={send}
            disabled={busy || !connected || !input.trim()}
            className="px-4 rounded-xl bg-sky-600 hover:bg-sky-500 disabled:opacity-40 disabled:cursor-not-allowed text-sm font-medium cursor-pointer"
          >
            {busy ? '…' : 'Send'}
          </button>
        </div>
      </footer>

      {showReports && <ReportsPanel onClose={() => setShowReports(false)} />}
    </div>
  )
}
