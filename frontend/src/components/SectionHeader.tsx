import type { ReactNode } from "react";

type Tone = "pos" | "neg" | "off";
const BAR: Record<Tone, string> = { pos: "bg-pos", neg: "bg-neg", off: "bg-off" };
const TEXT: Record<Tone, string> = { pos: "text-pos", neg: "text-neg", off: "text-muted" };

interface Props {
  tone: Tone;
  title: string;
  count: number;
  hint?: string;
  action?: ReactNode;
}

export function SectionHeader({ tone, title, count, hint, action }: Props) {
  return (
    <div className="mb-3 flex items-start gap-3">
      <span className={`mt-1 h-9 w-1 shrink-0 rounded-full ${BAR[tone]}`} aria-hidden="true" />
      <div className="min-w-0 flex-1">
        <h2 className={`flex items-center gap-2 text-base font-semibold ${TEXT[tone]}`}>
          {title}
          <span className="rounded-full bg-subtle px-2 py-0.5 text-xs font-medium text-muted">{count}</span>
        </h2>
        {hint && <p className="mt-0.5 text-xs text-muted">{hint}</p>}
      </div>
      {action}
    </div>
  );
}
