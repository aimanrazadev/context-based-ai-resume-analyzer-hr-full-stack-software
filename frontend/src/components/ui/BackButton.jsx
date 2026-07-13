import { ArrowLeft } from "lucide-react";
import "./BackButton.css";

export default function BackButton({ children = "Back", className = "", type = "button", ...props }) {
  return (
    <button type={type} className={`ds-back-button ${className}`.trim()} {...props}>
      <ArrowLeft aria-hidden="true" />
      <span>{children}</span>
    </button>
  );
}
