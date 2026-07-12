export default function PageHeader({ title, subtitle, actions, className = "" }) {
  return (
    <header className={`ds-page-header ${className}`.trim()}>
      <div>
        <h1 className="ds-page-title">{title}</h1>
        {subtitle && <p className="ds-page-subtitle">{subtitle}</p>}
      </div>
      {actions && <div>{actions}</div>}
    </header>
  );
}
