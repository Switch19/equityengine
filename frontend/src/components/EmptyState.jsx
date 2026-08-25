export default function EmptyState({ title, description, action }) {
  return (
    <div className="text-center py-12 px-4 border border-dashed border-ink-100 rounded-lg">
      <h3 className="font-display font-semibold text-ink">{title}</h3>
      {description && <p className="text-sm text-slate mt-1 max-w-sm mx-auto">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
