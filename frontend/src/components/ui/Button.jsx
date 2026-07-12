export default function Button({
  children,
  variant = "primary",
  className = "",
  type = "button",
  ...props
}) {
  return (
    <button type={type} className={`ds-btn ds-btn--${variant} ${className}`.trim()} {...props}>
      {children}
    </button>
  );
}
