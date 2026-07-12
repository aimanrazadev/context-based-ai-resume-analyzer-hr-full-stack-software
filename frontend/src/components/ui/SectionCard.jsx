export default function SectionCard({ title, children, actions, className = "" }) {
  return (
    <section className={`ds-section-card ${className}`.trim()}>
      {(title || actions) && (
        <div className="ds-section-card__header">
          {title && <h2 className="ds-card-title">{title}</h2>}
          {actions && <div>{actions}</div>}
        </div>
      )}
      {children}
    </section>
  );
}
