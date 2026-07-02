export default function SkeletonCard({ lines = 3 }) {
  return (
    <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6 animate-pulse">
      <div className="h-4 bg-gray-200 rounded w-1/3 mb-4"></div>
      {Array.from({ length: lines }).map((_, i) => (
        <div
          key={i}
          className={`h-3 bg-gray-100 rounded mb-2 ${
            i === lines - 1 ? 'w-2/3' : 'w-full'
          }`}
        />
      ))}
    </div>
  )
}

export function SkeletonStat() {
  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 animate-pulse">
      <div className="h-3 bg-gray-200 rounded w-1/2 mb-3"></div>
      <div className="h-8 bg-gray-100 rounded w-1/3"></div>
    </div>
  )
}