export default function EmptyState({ icon: Icon, title, description, action }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      {Icon && (
        <div className="w-16 h-16 rounded-2xl bg-surface-2 flex items-center justify-center mb-4">
          <Icon className="w-7 h-7 text-text-3" />
        </div>
      )}
      <h3 className="text-base font-semibold text-text-1 mb-1">{title}</h3>
      {description && <p className="text-sm text-text-2 max-w-sm">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
