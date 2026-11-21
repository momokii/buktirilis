import { Link } from "react-router-dom";

export function Brand({ to = "/projects", size = "default" }: { to?: string; size?: "default" | "large" }) {
  return (
    <Link className={`brand ${size === "large" ? "brand-large" : ""}`.trim()} to={to}>
      <img
        className="brand-logo"
        src="/logo-mark.svg"
        alt=""
        width={size === "large" ? 34 : 26}
        height={size === "large" ? 34 : 26}
      />
      <span>BuktiRilis</span>
    </Link>
  );
}
