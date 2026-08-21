import { X } from "lucide-react";

export default function Modal({ title, eyebrow, children, onClose }) {
  if (!children) return null;

  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <article className="modal" role="dialog" aria-modal="true" onClick={(event) => event.stopPropagation()}>
        <div className="modal-header">
          <div>
            {eyebrow && <span className="eyebrow">{eyebrow}</span>}
            <h2>{title}</h2>
          </div>
          <button type="button" onClick={onClose} aria-label="Close modal">
            <X size={18} />
          </button>
        </div>
        {children}
      </article>
    </div>
  );
}
