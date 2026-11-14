import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
} from "react";
import type {
  ButtonHTMLAttributes,
  HTMLAttributes,
  InputHTMLAttributes,
  ReactNode,
  SelectHTMLAttributes,
} from "react";
import { Link } from "react-router-dom";
import type { RetestMethod } from "./api";

/* ------------------------------------------------------------------ buttons */

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: "sm" | "md";
  busy?: boolean;
}

export function Button({
  variant = "secondary",
  size = "md",
  busy = false,
  className = "",
  children,
  disabled,
  ...rest
}: ButtonProps) {
  return (
    <button
      type="button"
      className={`btn btn-${variant} btn-${size} ${className}`.trim()}
      disabled={disabled || busy}
      aria-busy={busy || undefined}
      {...rest}
    >
      {busy ? <span className="btn-spinner" aria-hidden="true" /> : null}
      {children}
    </button>
  );
}

export function LinkButton({
  to,
  variant = "secondary",
  size = "md",
  children,
  className = "",
}: {
  to: string;
  variant?: ButtonVariant;
  size?: "sm" | "md";
  children: ReactNode;
  className?: string;
}) {
  return (
    <Link className={`btn btn-${variant} btn-${size} btn-link ${className}`.trim()} to={to}>
      {children}
    </Link>
  );
}

/* ------------------------------------------------------------------- badges */

const SEVERITY_LABELS: Record<string, string> = {
  critical: "Critical",
  high: "High",
  medium: "Medium",
  low: "Low",
  info: "Info",
};

export function SeverityBadge({ severity }: { severity: string }) {
  return (
    <span className={`sev sev-${severity}`}>
      <span className="sev-shape" aria-hidden="true" />
      {SEVERITY_LABELS[severity] ?? severity}
    </span>
  );
}

export function EvidenceBadge({ status }: { status: string }) {
  if (status === "needs_validation") {
    return (
      <span className="badge badge-warn">
        <span aria-hidden="true">▲</span> Needs validation
      </span>
    );
  }
  return (
    <span className="badge badge-neutral">
      <span aria-hidden="true">✓</span> Evidence supported
    </span>
  );
}

export function VerdictBadge({ outcome }: { outcome: string }) {
  const map: Record<string, [string, string, string]> = {
    fix_verified: ["badge-pass", "✓", "Fix verified"],
    still_reproducible: ["badge-fail", "◆", "Still reproducible"],
    inconclusive: ["badge-warn", "▲", "Inconclusive"],
    awaiting_retest: ["badge-pending", "○", "Awaiting retest"],
    observed: ["badge-fail", "◆", "Observed"],
    not_observed: ["badge-pass", "✓", "Not observed"],
    new: ["badge-info", "＋", "New"],
  };
  const [tone, icon, label] = map[outcome] ?? ["badge-neutral", "•", outcome.replace(/_/g, " ")];
  return (
    <span className={`badge ${tone}`}>
      <span aria-hidden="true">{icon}</span> {label}
    </span>
  );
}

export function StatusBadge({ status }: { status: string }) {
  const map: Record<string, [string, string]> = {
    queued: ["badge-pending", "Queued"],
    running: ["badge-info", "Running"],
    cancel_requested: ["badge-warn", "Cancel requested"],
    completed: ["badge-pass", "Completed"],
    failed: ["badge-fail", "Failed"],
    canceled: ["badge-neutral", "Canceled"],
    interrupted: ["badge-warn", "Interrupted"],
    succeeded: ["badge-pass", "Succeeded"],
  };
  const [tone, label] = map[status] ?? ["badge-neutral", status];
  return <span className={`badge ${tone}`}>{label}</span>;
}

export function CoverageBadge({ result }: { result: string }) {
  const map: Record<string, [string, string]> = {
    tested_no_finding: ["badge-pass", "Tested — no finding"],
    finding_observed: ["badge-fail", "Finding observed"],
    blocked: ["badge-warn", "Blocked"],
    not_run: ["badge-neutral", "Not run"],
    not_applicable: ["badge-neutral", "Not applicable"],
    needs_review: ["badge-warn", "Needs review"],
    planned: ["badge-pending", "Planned"],
  };
  const [tone, label] = map[result] ?? ["badge-neutral", result.replace(/_/g, " ")];
  return <span className={`badge ${tone}`}>{label}</span>;
}

export function ModeBadge({ mode }: { mode: string }) {
  return (
    <span className={`badge ${mode === "demo" ? "badge-demo" : "badge-info"}`}>
      {mode === "demo" ? "Demo · deterministic fixtures" : "Live engine"}
    </span>
  );
}

export function MethodBadge({ method }: { method: RetestMethod }) {
  const map: Record<string, string> = {
    automatic: "Automatic replay",
    guided: "Guided retest",
    pending_evidence_review: "Review evidence",
  };
  return <span className="badge badge-neutral">{map[method] ?? method}</span>;
}

/* --------------------------------------------------------------------- tabs */

export interface TabItem {
  id: string;
  label: string;
  count?: number;
}

export function Tabs({
  items,
  value,
  onChange,
  label,
  children,
}: {
  items: TabItem[];
  value: string;
  onChange: (id: string) => void;
  label: string;
  children: ReactNode;
}) {
  const baseId = useId();
  const refs = useRef<Record<string, HTMLButtonElement | null>>({});

  const onKeyDown = (event: React.KeyboardEvent<HTMLButtonElement>, index: number) => {
    let nextIndex: number | null = null;
    if (event.key === "ArrowRight") nextIndex = (index + 1) % items.length;
    if (event.key === "ArrowLeft") nextIndex = (index - 1 + items.length) % items.length;
    if (event.key === "Home") nextIndex = 0;
    if (event.key === "End") nextIndex = items.length - 1;
    if (nextIndex === null) return;
    event.preventDefault();
    const next = items[nextIndex];
    onChange(next.id);
    refs.current[next.id]?.focus();
  };

  return (
    <div className="tabs">
      <div className="tablist" role="tablist" aria-label={label}>
        {items.map((item, index) => (
          <button
            key={item.id}
            ref={(node) => {
              refs.current[item.id] = node;
            }}
            role="tab"
            type="button"
            id={`${baseId}-tab-${item.id}`}
            aria-selected={item.id === value}
            aria-controls={`${baseId}-panel-${item.id}`}
            tabIndex={item.id === value ? 0 : -1}
            className={`tab ${item.id === value ? "tab-active" : ""}`}
            onClick={() => onChange(item.id)}
            onKeyDown={(event) => onKeyDown(event, index)}
          >
            {item.label}
            {typeof item.count === "number" ? (
              <span className="tab-count" aria-hidden="true">
                {item.count}
              </span>
            ) : null}
          </button>
        ))}
      </div>
      <div
        role="tabpanel"
        id={`${baseId}-panel-${value}`}
        aria-labelledby={`${baseId}-tab-${value}`}
        tabIndex={0}
        className="tabpanel"
      >
        {children}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ dialogs */

export function Dialog({
  open,
  onClose,
  title,
  description,
  children,
  footer,
  wide = false,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children: ReactNode;
  footer?: ReactNode;
  wide?: boolean;
}) {
  const ref = useRef<HTMLDialogElement | null>(null);
  const titleId = useId();
  const descriptionId = useId();

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      className={`dialog ${wide ? "dialog-wide" : ""}`}
      aria-labelledby={titleId}
      aria-describedby={description ? descriptionId : undefined}
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
      onClose={onClose}
      onClick={(event) => {
        if (event.target === ref.current) onClose();
      }}
    >
      <div className="dialog-inner">
        <header className="dialog-header">
          <h2 id={titleId}>{title}</h2>
          <button type="button" className="dialog-close" onClick={onClose} aria-label="Close dialog">
            ×
          </button>
        </header>
        {description ? (
          <p className="dialog-description" id={descriptionId}>
            {description}
          </p>
        ) : null}
        <div className="dialog-body">{children}</div>
        {footer ? <footer className="dialog-footer">{footer}</footer> : null}
      </div>
    </dialog>
  );
}

/* ------------------------------------------------------------------- fields */

export function Field({
  label,
  hint,
  error,
  children,
  htmlFor,
}: {
  label: string;
  hint?: string;
  error?: string;
  children: ReactNode;
  htmlFor: string;
}) {
  return (
    <div className="field">
      <label htmlFor={htmlFor}>{label}</label>
      {children}
      {hint ? <p className="field-hint">{hint}</p> : null}
      {error ? (
        <p className="field-error" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}

export function TextInput(props: InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={`input ${props.className ?? ""}`.trim()} />;
}

export function Select(props: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select {...props} className={`input select ${props.className ?? ""}`.trim()} />;
}

/* ------------------------------------------------------------------ feedback */

export function Loading({ label = "Loading" }: { label?: string }) {
  return (
    <div className="loading" role="status">
      <span className="spinner" aria-hidden="true" />
      <span>{label}…</span>
    </div>
  );
}

export function ErrorState({
  message,
  onRetry,
  detail,
}: {
  message: string;
  onRetry?: () => void;
  detail?: string;
}) {
  return (
    <div className="state state-error" role="alert">
      <h3>We could not load this view</h3>
      <p>{message}</p>
      {detail ? <pre className="code" tabIndex={0} role="region" aria-label="Scrollable code excerpt">{detail}</pre> : null}
      {onRetry ? (
        <Button variant="secondary" onClick={onRetry}>
          Try again
        </Button>
      ) : null}
    </div>
  );
}

export function EmptyState({
  title,
  children,
  action,
}: {
  title: string;
  children?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="state state-empty">
      <h3>{title}</h3>
      {children ? <div className="state-body">{children}</div> : null}
      {action}
    </div>
  );
}

export function Notice({
  tone = "info",
  title,
  children,
  action,
}: {
  tone?: "info" | "warn" | "error" | "success";
  title?: string;
  children?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className={`notice notice-${tone}`}>
      <div>
        {title ? <strong>{title}</strong> : null}
        {title && children ? " " : null}
        {children}
      </div>
      {action ? <div className="notice-action">{action}</div> : null}
    </div>
  );
}

/* -------------------------------------------------------------------- toasts */

interface ToastItem {
  id: number;
  tone: "info" | "success" | "error";
  message: string;
}

interface ToastValue {
  notify: (tone: ToastItem["tone"], message: string) => void;
}

const ToastContext = createContext<ToastValue | null>(null);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);

  const notify = useCallback((tone: ToastItem["tone"], message: string) => {
    const id = Date.now() + Math.random();
    setItems((current) => [...current, { id, tone, message }]);
    window.setTimeout(() => {
      setItems((current) => current.filter((item) => item.id !== id));
    }, 7000);
  }, []);

  const value = useMemo(() => ({ notify }), [notify]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="toasts" role="status" aria-live="polite">
        {items.map((item) => (
          <div key={item.id} className={`toast toast-${item.tone}`}>
            {item.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastValue {
  const context = useContext(ToastContext);
  if (!context) throw new Error("useToast must be used inside ToastProvider");
  return context;
}

/* ---------------------------------------------------------------- primitives */

export function Mono({ children, wrap = false }: { children: ReactNode; wrap?: boolean }) {
  return <code className={wrap ? "mono mono-wrap" : "mono"}>{children}</code>;
}

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
  meta,
}: {
  eyebrow?: ReactNode;
  title: string;
  description?: ReactNode;
  actions?: ReactNode;
  meta?: ReactNode;
}) {
  return (
    <header className="page-header">
      <div className="page-header-main">
        {eyebrow ? <div className="eyebrow">{eyebrow}</div> : null}
        <h1>{title}</h1>
        {description ? <p className="page-description">{description}</p> : null}
        {meta ? <div className="page-meta">{meta}</div> : null}
      </div>
      {actions ? <div className="page-actions">{actions}</div> : null}
    </header>
  );
}

export function Breadcrumbs({
  items,
}: {
  items: { label: string; to?: string }[];
}) {
  return (
    <nav className="breadcrumbs" aria-label="Breadcrumb">
      <ol>
        {items.map((item, index) => (
          <li key={`${item.label}-${index}`}>
            {item.to ? <Link to={item.to}>{item.label}</Link> : <span aria-current="page">{item.label}</span>}
          </li>
        ))}
      </ol>
    </nav>
  );
}

export function DefinitionList({
  items,
  className = "",
}: {
  items: { term: string; value: ReactNode; mono?: boolean }[];
  className?: string;
}) {
  return (
    <dl className={`definitions ${className}`.trim()}>
      {items.map((item) => (
        <div key={item.term} className="definition">
          <dt>{item.term}</dt>
          <dd className={item.mono ? "mono" : undefined}>{item.value}</dd>
        </div>
      ))}
    </dl>
  );
}

export function InlineCodeList({ values }: { values: string[] }) {
  if (values.length === 0) return <span className="muted">None</span>;
  return (
    <ul className="inline-code-list">
      {values.map((value) => (
        <li key={value}>
          <Mono>{value}</Mono>
        </li>
      ))}
    </ul>
  );
}

export function Section({
  title,
  description,
  children,
  actions,
  id,
}: {
  title: string;
  description?: ReactNode;
  children: ReactNode;
  actions?: ReactNode;
  id?: string;
}) {
  const headingId = useId();
  return (
    <section className="section" aria-labelledby={headingId} id={id}>
      <div className="section-header">
        <div>
          <h2 id={headingId}>{title}</h2>
          {description ? <p className="section-description">{description}</p> : null}
        </div>
        {actions ? <div className="section-actions">{actions}</div> : null}
      </div>
      {children}
    </section>
  );
}

export function KeyValuePill({ label, value }: { label: string; value: string }) {
  return (
    <span className="kv-pill">
      <span className="kv-label">{label}</span>
      <span className="kv-value">{value}</span>
    </span>
  );
}

export function RelativeTime({ value, compact = false }: { value: string | null; compact?: boolean }) {
  if (!value) return <span className="muted">—</span>;
  const date = new Date(value);
  const iso = date.toISOString().replace(".000Z", "Z");
  return (
    <time dateTime={iso} title={iso} className="nowrap">
      {compact
        ? date.toLocaleString("sv-SE", {
            year: "numeric",
            month: "2-digit",
            day: "2-digit",
            hour: "2-digit",
            minute: "2-digit",
          })
        : date.toLocaleString(undefined, {
            year: "numeric",
            month: "short",
            day: "2-digit",
            hour: "2-digit",
            minute: "2-digit",
          })}
    </time>
  );
}

export function Stat({
  label,
  value,
  to,
  tone,
  hint,
}: {
  label: string;
  value: number | string;
  to?: string;
  tone?: "fail" | "warn" | "pass" | "info";
  hint?: string;
}) {
  const body = (
    <>
      <span className="stat-label">{label}</span>
      <span className="stat-value">{value}</span>
      {hint ? <span className="stat-hint">{hint}</span> : null}
    </>
  );
  if (to) {
    return (
      <Link className={`stat stat-link ${tone ? `stat-${tone}` : ""}`.trim()} to={to}>
        {body}
      </Link>
    );
  }
  return <div className={`stat ${tone ? `stat-${tone}` : ""}`.trim()}>{body}</div>;
}

export function TableWrap({ children, label }: { children: ReactNode; label: string }) {
  return (
    <div className="table-wrap" role="region" aria-label={label} tabIndex={0}>
      {children}
    </div>
  );
}

export function Th({
  children,
  ...rest
}: HTMLAttributes<HTMLTableCellElement> & { scope?: "col" | "row" }) {
  return <th {...rest}>{children}</th>;
}
