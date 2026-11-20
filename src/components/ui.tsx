import { useState, useEffect, useRef, type ReactNode } from "react";
import { Box, Loader2, Waves, X, type LucideIcon } from "lucide-react";
import { date, human, type Reading } from "../api";

export const colors = {
  teal: "#3478df",
  lime: "#50b89b",
  amber: "#dfad52",
  red: "#d67e8d",
  blue: "#879bca",
};
export function initials(name: string) {
  return name
    .split(" ")
    .map((x) => x[0])
    .slice(0, 2)
    .join("");
}
export function Badge({
  value,
  children,
}: {
  value: string;
  children?: ReactNode;
}) {
  return (
    <span className={`badge ${value}`}>
      <span />
      {children || human(value)}
    </span>
  );
}
export function Button({
  children,
  icon: Icon,
  className = "",
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { icon?: LucideIcon }) {
  return (
    <button className={`btn ${className}`} {...props}>
      {Icon && <Icon size={16} />}
      {children}
    </button>
  );
}
export function Empty({
  icon: Icon = Box,
  title,
  description,
  action,
}: {
  icon?: LucideIcon;
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="empty">
      <span className="empty-icon">
        <Icon size={27} />
      </span>
      <h3>{title}</h3>
      <p>{description}</p>
      {action}
    </div>
  );
}
export function Spinner() {
  return (
    <div className="loading">
      <Loader2 className="spin" size={24} />
      <span>Connecting your workspace…</span>
    </div>
  );
}
export function Modal({
  title,
  description,
  children,
  onClose,
  wide = false,
}: {
  title: string;
  description?: string;
  children: ReactNode;
  onClose: () => void;
  wide?: boolean;
}) {
  const root = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const el = root.current;
    el?.querySelector<HTMLElement>("input, button, textarea, select")?.focus();
    function keys(e: KeyboardEvent) {
      const dialogs = document.querySelectorAll('[role="dialog"]');
      if (dialogs[dialogs.length - 1] !== el) return;
      if (e.key === "Escape") onClose();
      if (e.key === "Tab" && el) {
        const nodes = Array.from(
          el.querySelectorAll<HTMLElement>(
            "button:not([disabled]), input, textarea, select, a[href]",
          ),
        ).filter((n) => n.offsetParent !== null);
        const first = nodes[0],
          last = nodes[nodes.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last?.focus();
        }
        if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first?.focus();
        }
      }
    }
    document.addEventListener("keydown", keys);
    const old = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", keys);
      document.body.style.overflow = old;
      previous?.focus();
    };
  }, [onClose]);
  return (
    <div
      className="modal-backdrop"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        className={`modal ${wide ? "wide" : ""}`}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        ref={root}
      >
        <div className="modal-head">
          <div>
            <h2>{title}</h2>
            {description && <p>{description}</p>}
          </div>
          <button
            className="icon-btn"
            aria-label="Close dialog"
            onClick={onClose}
          >
            <X size={20} />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
export function Chart({
  data,
  field = "vibration",
  color = colors.teal,
  large = false,
  threshold,
}: {
  data: Reading[];
  field?: keyof Pick<
    Reading,
    "vibration" | "temperature" | "pressure" | "flow"
  >;
  color?: string;
  large?: boolean;
  threshold?: number;
}) {
  const [hover, setHover] = useState<number | null>(null);
  if (!data.length)
    return (
      <Empty
        title="Waiting for readings"
        description="Ingest a sensor snapshot to start this trend."
        icon={Waves}
      />
    );
  const width = 760,
    height = large ? 265 : 195,
    pad = { l: 40, r: 18, t: 22, b: 30 };
  const values = data.map((x) => x[field]);
  const min = Math.max(0, Math.min(...values, threshold ?? Infinity) * 0.78),
    max = Math.max(...values, threshold ?? 0) * 1.18;
  const x = (i: number) =>
    pad.l + (i / Math.max(1, data.length - 1)) * (width - pad.l - pad.r);
  const y = (v: number) =>
    height - pad.b - ((v - min) / (max - min || 1)) * (height - pad.t - pad.b);
  const d = values
    .map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(2)},${y(v).toFixed(2)}`)
    .join(" ");
  const id = `fill-${field}-${large ? 1 : 0}`;
  const unit = {
    vibration: "mm/s",
    temperature: "°C",
    pressure: "bar",
    flow: "m³/h",
  }[field];
  return (
    <div className="chart">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label={`${field} trend in ${unit}`}
        onMouseLeave={() => setHover(null)}
        onMouseMove={(e) => {
          const r = e.currentTarget.getBoundingClientRect();
          const px = ((e.clientX - r.left) / r.width) * width;
          setHover(
            Math.max(
              0,
              Math.min(
                data.length - 1,
                Math.round(
                  ((px - pad.l) / (width - pad.l - pad.r)) * (data.length - 1),
                ),
              ),
            ),
          );
        }}
      >
        <defs>
          <linearGradient id={id} x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity=".2" />
            <stop offset="100%" stopColor={color} stopOpacity="0" />
          </linearGradient>
        </defs>
        {[0, 1, 2, 3].map((i) => {
          const v = min + ((max - min) * i) / 3;
          return (
            <g key={i}>
              <line
                x1={pad.l}
                x2={width - pad.r}
                y1={y(v)}
                y2={y(v)}
                stroke="#ededed"
                strokeDasharray="3 5"
              />
              <text
                x={pad.l - 12}
                y={y(v) + 4}
                textAnchor="end"
                fill="#7285a0"
                fontSize="12"
              >
                {v.toFixed(field === "flow" || field === "temperature" ? 0 : 1)}
              </text>
            </g>
          );
        })}
        {threshold && (
          <g>
            <line
              x1={pad.l}
              x2={width - pad.r}
              y1={y(threshold)}
              y2={y(threshold)}
              stroke="#c49a48"
              strokeDasharray="6 5"
            />
            <text
              x={width - pad.r - 5}
              y={y(threshold) - 7}
              textAnchor="end"
              fill="#a27b35"
              fontSize="12"
            >
              Demo review limit · {threshold}
            </text>
          </g>
        )}
        <path
          d={`${d} L${x(values.length - 1)},${height - pad.b} L${pad.l},${height - pad.b}Z`}
          fill={`url(#${id})`}
        />
        <path
          d={d}
          fill="none"
          stroke={color}
          strokeWidth="2.5"
          strokeLinejoin="round"
          strokeLinecap="round"
        />
        {[0, 0.25, 0.5, 0.75, 1].map((part, i) => {
          const idx = Math.round(part * (data.length - 1));
          return (
            <text
              key={i}
              x={x(idx)}
              y={height - 7}
              textAnchor={i === 0 ? "start" : i === 4 ? "end" : "middle"}
              fill="#7285a0"
              fontSize="12"
            >
              {date(data[idx].timestamp)}
            </text>
          );
        })}
        {hover !== null && (
          <g>
            <line
              x1={x(hover)}
              x2={x(hover)}
              y1={pad.t}
              y2={height - pad.b}
              stroke="#838383"
              strokeDasharray="3 3"
            />
            <circle
              cx={x(hover)}
              cy={y(values[hover])}
              r="4"
              fill={color}
              stroke="white"
              strokeWidth="2"
            />
            <rect
              x={Math.min(width - 150, Math.max(45, x(hover) - 55))}
              y="0"
              width="125"
              height="23"
              rx="5"
              fill="#323232"
            />
            <text
              x={Math.min(width - 150, Math.max(45, x(hover) - 55)) + 62}
              y="15"
              fill="white"
              fontSize="12"
              textAnchor="middle"
            >
              {values[hover].toFixed(2)} {unit} · {date(data[hover].timestamp)}
            </text>
          </g>
        )}
      </svg>
    </div>
  );
}
export function MiniSpark({
  seed = 1,
  critical = false,
  values,
  decorative = true,
}: {
  seed?: number;
  critical?: boolean;
  values?: number[];
  decorative?: boolean;
}) {
  const illustrated = Array.from(
    { length: 28 },
    (_, i) =>
      23 +
      Math.sin(i * 0.6 + seed) * 5 +
      Math.cos(i * 0.9) * 3 -
      (critical ? i * 0.5 : 0),
  );
  const raw = values || [];
  const low = Math.min(...raw),
    high = Math.max(...raw);
  const vals = decorative
    ? illustrated
    : raw.map((v) => 29 - ((v - low) / (high - low || 1)) * 23);
  return (
    <svg className="mini-spark" viewBox="0 0 110 35" aria-hidden="true">
      <path
        d={vals
          .map(
            (v, i) =>
              `${i ? "L" : "M"}${(i / Math.max(1, vals.length - 1)) * 108},${v}`,
          )
          .join(" ")}
        fill="none"
        stroke={critical ? colors.amber : colors.teal}
        strokeWidth="1.8"
      />
    </svg>
  );
}
export function EquipmentArt({
  kind = "Pump",
  size = "normal",
}: {
  kind?: string;
  size?: string;
}) {
  return (
    <svg
      className={`equipment-art ${size}`}
      viewBox="0 0 240 140"
      role="img"
      aria-label={`${kind} equipment schematic`}
    >
      <defs>
        <linearGradient id="metal" x1="0" y1="0" x2="1" y2="1">
          <stop stopColor="#d2deee" />
          <stop offset="1" stopColor="#a8b4c4" />
        </linearGradient>
      </defs>
      <ellipse cx="125" cy="119" rx="90" ry="10" fill="#cfdbeb" opacity=".55" />
      <path d="M28 108 182 108 216 122 62 122Z" fill="#b5c1d1" />
      <path d="M28 108v7l34 14v-7m154 0v7L62 129" fill="#9ba7b7" />
      {kind === "Motor" || kind === "Turbine" ? (
        <g>
          <path d="M62 52 122 33 180 54v46l-60 20-58-22Z" fill="url(#metal)" />
          <ellipse cx="168" cy="76" rx="25" ry="28" fill="#8591a1" />
          <ellipse cx="168" cy="76" rx="13" ry="16" fill="#d0dcec" />
          <path
            d="m75 54 0 39m11-43v46m12-50v48m12-52v48"
            stroke="#8c98a8"
            strokeWidth="3"
          />
          <path d="m180 72 34-4v10l-34 5" fill="#8591a1" />
        </g>
      ) : (
        <g>
          <path d="m58 88 64-20 40 16-63 22Z" fill="#94a0b0" />
          <path d="M54 60 92 45l36 14v34L91 107 54 92Z" fill="url(#metal)" />
          <ellipse cx="124" cy="75" rx="21" ry="25" fill="#a3afbf" />
          <ellipse cx="124" cy="75" rx="10" ry="13" fill="#6d7989" />
          <path
            d="m70 59 0 29m10-33v37m10-41v43"
            stroke="#95a1b1"
            strokeWidth="3"
          />
          <path d="m145 75 24-7v14l-24 7" fill="#8793a3" />
          <ellipse cx="178" cy="78" rx="26" ry="27" fill="#8b97a7" />
          <ellipse cx="178" cy="78" rx="19" ry="20" fill="#bdc9d9" />
          <ellipse cx="178" cy="78" rx="7" ry="9" fill="#7e8a9a" />
          <path d="M172 57V31l17-5 10 5v24" fill="#a0acbc" />
          <ellipse cx="185" cy="29" rx="14" ry="6" fill="#7c8898" />
          <path d="M185 79h28v14h-28" fill="#adb9c9" />
          <ellipse cx="213" cy="86" rx="7" ry="11" fill="#8591a1" />
        </g>
      )}
      <path d="m58 100 0 12m110-12v13" stroke="#7e8a9a" strokeWidth="7" />
      <circle cx="46" cy="113" r="2" fill="#677383" />
      <circle cx="186" cy="118" r="2" fill="#677383" />
    </svg>
  );
}
