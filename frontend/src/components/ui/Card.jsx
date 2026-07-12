export default function Card({ children, className = "", clickable = false, ...props }) {
  return (
    <div className={`ds-card ${clickable ? "ds-clickable-card" : ""} ${className}`.trim()} {...props}>
      {children}
    </div>
  );
}
