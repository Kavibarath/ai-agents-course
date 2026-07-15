import { useState } from 'react'

const TOOL_META = {
  calculator: { icon: '🧮', label: 'Calculating' },
  get_current_datetime: { icon: '🕒', label: 'Checking the clock' },
  web_search: { icon: '🔎', label: 'Searching the web' },
  run_python: { icon: '🐍', label: 'Running Python' },
  research_topic: { icon: '📚', label: 'Deep research' },
}

function Spinner() {
  return (
    <span className="inline-block size-3.5 rounded-full border-2 border-zinc-600 border-t-sky-400 animate-spin" />
  )
}

// One collapsible trace card: the Act + Observe steps of the agent loop.
export default function ToolStep({ step }) {
  const [open, setOpen] = useState(false)
  const meta = TOOL_META[step.name] ?? { icon: '🔧', label: step.name }
  const status = step.pending ? (
    <Spinner />
  ) : step.declined ? (
    <span className="text-red-400 text-xs font-medium">rejected</span>
  ) : (
    <span className="text-emerald-400 text-xs">✓</span>
  )

  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-900/60 text-sm">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-2.5 px-3 py-2 text-left hover:bg-zinc-800/50 rounded-lg cursor-pointer"
      >
        <span>{meta.icon}</span>
        <span className="text-zinc-300">
          {meta.label}
          {step.pending && <span className="text-zinc-500">…</span>}
        </span>
        <span className="ml-auto flex items-center gap-2">
          {status}
          <span className="text-zinc-600 text-xs">{open ? '▲' : '▼'}</span>
        </span>
      </button>

      {open && (
        <div className="border-t border-zinc-800 px-3 py-2 space-y-2">
          <div>
            <div className="text-[11px] uppercase tracking-wide text-zinc-500 mb-1">
              {step.name} — arguments
            </div>
            <pre className="bg-zinc-950 border border-zinc-800 rounded-md p-2 text-xs text-zinc-300 overflow-x-auto whitespace-pre-wrap">
              {step.args?.code ?? JSON.stringify(step.args, null, 2)}
            </pre>
          </div>
          {!step.pending && (
            <div>
              <div className="text-[11px] uppercase tracking-wide text-zinc-500 mb-1">result</div>
              <pre className="bg-zinc-950 border border-zinc-800 rounded-md p-2 text-xs text-zinc-400 overflow-x-auto whitespace-pre-wrap max-h-56 overflow-y-auto">
                {step.result}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
