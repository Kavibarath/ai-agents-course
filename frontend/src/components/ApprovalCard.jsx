// Week 2's human-in-the-loop, in the browser: the agent wrote this code and
// is blocked server-side until the user decides.
export default function ApprovalCard({ approval, onDecide }) {
  return (
    <div className="rounded-lg border border-amber-500/40 bg-amber-500/5 p-3 text-sm space-y-2">
      <div className="flex items-center gap-2 text-amber-300 font-medium">
        <span>⚠️</span> Approval required — the agent wants to run this code
      </div>
      <pre className="bg-zinc-950 border border-zinc-800 rounded-md p-2 text-xs text-zinc-200 overflow-x-auto whitespace-pre-wrap">
        {approval.args?.code ?? JSON.stringify(approval.args, null, 2)}
      </pre>

      {approval.status === 'pending' ? (
        <div className="flex gap-2">
          <button
            onClick={() => onDecide(true)}
            className="px-3 py-1.5 rounded-md bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-medium cursor-pointer"
          >
            Approve &amp; run
          </button>
          <button
            onClick={() => onDecide(false)}
            className="px-3 py-1.5 rounded-md bg-zinc-800 hover:bg-red-600/80 text-zinc-200 text-xs font-medium cursor-pointer"
          >
            Reject
          </button>
        </div>
      ) : (
        <div className={approval.status === 'approved' ? 'text-emerald-400 text-xs' : 'text-red-400 text-xs'}>
          {approval.status === 'approved' ? '✓ Approved — code was executed' : '✕ Rejected — code was not run'}
        </div>
      )}
    </div>
  )
}
