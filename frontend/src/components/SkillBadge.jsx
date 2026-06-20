export default function SkillBadge({ skill }) {
  return (
    <span className="inline-block bg-blue-100 text-blue-700 text-xs font-medium px-3 py-1 rounded-full mr-2 mb-2 capitalize">
      {skill}
    </span>
  )
}