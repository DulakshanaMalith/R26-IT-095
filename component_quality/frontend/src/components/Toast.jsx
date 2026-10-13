import { CheckCircle2, Info, TriangleAlert, X } from "lucide-react";

function ToastIcon({ type }) {
  if (type === "success") return <CheckCircle2 size={18} />;
  if (type === "error") return <TriangleAlert size={18} />;
  return <Info size={18} />;
}

export default function ToastContainer({ toasts = [], onDismiss }) {
  if (!toasts.length) return null;

  return (
    <div className="toast-stack" aria-live="polite">
      {toasts.map((toast) => (
        <article className={`toast-card ${toast.type || "info"}`} key={toast.id}>
          <ToastIcon type={toast.type} />
          <span>{toast.message}</span>
          <button type="button" onClick={() => onDismiss(toast.id)} aria-label="Dismiss notification">
            <X size={14} />
          </button>
        </article>
      ))}
    </div>
  );
}
