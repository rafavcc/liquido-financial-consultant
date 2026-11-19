import type { Alert } from "../api/types";
import { ALERT_META, type AlertTone } from "../lib/labels";

export const TONE: Record<AlertTone, string> = {
  warn: "bg-warn-bg text-warn",
  neg: "bg-neg-bg text-neg",
  off: "bg-off-bg text-off",
  info: "bg-subtle text-muted",
};

/** Alertas cujo texto dinâmico (datas, dias) vale mais que o rótulo curto. */
const SHOW_MESSAGE = new Set(["RESGATE_DN", "PARADO", "VENCIDO"]);

export function AlertBadge({ alert }: { alert: Alert }) {
  const meta = ALERT_META[alert.code] ?? { icon: "ℹ️", text: alert.message, tone: "info" as const };
  const text = SHOW_MESSAGE.has(alert.code) ? alert.message : meta.text;
  return (
    <span
      title={alert.message}
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium leading-4 ${TONE[meta.tone]}`}
    >
      <span aria-hidden="true">{meta.icon}</span>
      {text}
    </span>
  );
}
