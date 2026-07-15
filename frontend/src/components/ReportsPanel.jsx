import { useEffect, useState } from 'react'
import Markdown from './Markdown.jsx'

// Slide-over panel for the Week 4 research reports: list, read, download.
export default function ReportsPanel({ onClose }) {
  const [reports, setReports] = useState([])
  const [selected, setSelected] = useState(null) // {name, content}

  useEffect(() => {
    fetch('/api/reports')
      .then((r) => r.json())
      .then(setReports)
      .catch(() => setReports([]))
  }, [])

  const openReport = (name) => {
    fetch(`/api/reports/${encodeURIComponent(name)}`)
      .then((r) => r.json())
      .then(setSelected)
      .catch(() => {})
  }

  const download = () => {
    const blob = new Blob([selected.content], { type: 'text/markdown' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = selected.name
    a.click()
    URL.revokeObjectURL(a.href)
  }

  return (
    <div className="fixed inset-0 z-20 flex">
      <div className="flex-1 bg-black/60" onClick={onClose} />
      <div className="w-full max-w-2xl h-full bg-zinc-950 border-l border-zinc-800 flex flex-col">
        <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-800">
          <h2 className="text-sm font-semibold text-zinc-200">
            {selected ? selected.name : 'Research reports'}
          </h2>
          <div className="flex gap-2">
            {selected && (
              <>
                <button
                  onClick={download}
                  className="px-2.5 py-1 rounded-md bg-zinc-800 hover:bg-zinc-700 text-xs text-zinc-200 cursor-pointer"
                >
                  ⬇ Download .md
                </button>
                <button
                  onClick={() => setSelected(null)}
                  className="px-2.5 py-1 rounded-md bg-zinc-800 hover:bg-zinc-700 text-xs text-zinc-200 cursor-pointer"
                >
                  ← All reports
                </button>
              </>
            )}
            <button
              onClick={onClose}
              className="px-2.5 py-1 rounded-md bg-zinc-800 hover:bg-zinc-700 text-xs text-zinc-200 cursor-pointer"
            >
              ✕
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-4">
          {selected ? (
            <Markdown>{selected.content}</Markdown>
          ) : reports.length === 0 ? (
            <p className="text-sm text-zinc-500">
              No reports yet — ask the agent to “research” a topic.
            </p>
          ) : (
            <ul className="space-y-1">
              {reports.map((name) => (
                <li key={name}>
                  <button
                    onClick={() => openReport(name)}
                    className="w-full text-left px-3 py-2 rounded-md hover:bg-zinc-800/70 text-sm text-zinc-300 cursor-pointer"
                  >
                    📄 {name}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  )
}
