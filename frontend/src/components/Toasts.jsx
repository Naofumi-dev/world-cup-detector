// Transient top-right notifications.
export default function Toasts({ toasts, onDismiss }) {
  return (
    <div className="toasts" role="status" aria-live="polite">
      {toasts.map((t) => (
        <div className={`toast ${t.kind}`} key={t.id} onClick={() => onDismiss(t.id)}>
          <span className="toast-dot" />
          <span>{t.msg}</span>
        </div>
      ))}
    </div>
  );
}
