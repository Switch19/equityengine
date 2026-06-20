export default function SuggestionCard({ suggestion, onApprove, onReject, approved, rejected }) {
  return (
    <div className={`border rounded-xl p-4 mb-3 transition-all ${
      approved ? 'border-green-400 bg-green-50' : 
      rejected ? 'border-red-300 bg-red-50' : 
      'border-amber-300 bg-amber-50'
    }`}>
      <div className="flex justify-between items-start gap-4">
        <div className="flex-1">
          <p className="text-xs font-semibold text-gray-500 uppercase mb-1">Original Term</p>
          <p className="text-sm font-bold text-gray-800 mb-2">"{suggestion.original}"</p>
          <p className="text-xs font-semibold text-gray-500 uppercase mb-1">Global Equivalent</p>
          <p className="text-sm text-gray-700">{suggestion.suggestion}</p>
          <p className="text-xs text-amber-600 mt-2">⚠️ {suggestion.reason}</p>
        </div>

        {!approved && !rejected && (
          <div className="flex flex-col gap-2 shrink-0">
            <button
              onClick={onApprove}
              className="bg-green-500 hover:bg-green-600 text-white text-xs px-3 py-1.5 rounded-lg transition"
            >
              ✓ Approve
            </button>
            <button
              onClick={onReject}
              className="bg-red-400 hover:bg-red-500 text-white text-xs px-3 py-1.5 rounded-lg transition"
            >
              ✗ Reject
            </button>
          </div>
        )}

        {approved && (
          <span className="text-green-600 font-bold text-sm shrink-0">✓ Approved</span>
        )}
        {rejected && (
          <span className="text-red-500 font-bold text-sm shrink-0">✗ Rejected</span>
        )}
      </div>
    </div>
  )
}