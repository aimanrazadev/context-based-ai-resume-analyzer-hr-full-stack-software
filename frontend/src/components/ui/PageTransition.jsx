export default function PageTransition({ children, className = "" }) {
  return <div className={`ds-page-transition ${className}`.trim()}>{children}</div>;
}
