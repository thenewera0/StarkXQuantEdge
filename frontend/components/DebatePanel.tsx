import type { Decision } from "@/lib/api";
import { Card, Ring, SignalBadge } from "./ui";
import { TrendingUp, TrendingDown, Scale, CheckCircle2, AlertTriangle, XCircle, Sparkles } from "lucide-react";

const AGREEMENT: Record<string, { badge: string; label: string; icon: React.ReactNode }> = {
  agree: { badge: "bg-[var(--profit-dim)] text-[var(--profit)] border-[var(--profit)]/25", label: "AI agrees with the model", icon: <CheckCircle2 size={14} /> },
  caution: { badge: "bg-[var(--warn-dim)] text-amber-700 border-[var(--warn)]/25", label: "AI urges caution", icon: <AlertTriangle size={14} /> },
  disagree: { badge: "bg-[var(--loss-dim)] text-[var(--loss)] border-[var(--loss)]/25", label: "AI disagrees with the model", icon: <XCircle size={14} /> },
};

export function DebatePanel({ d }: { d: Decision }) {
  const debate = d.debate;
  const ag = AGREEMENT[debate.agreement] ?? AGREEMENT.caution;

  return (
    <div className="space-y-4">
      {/* Final verdict */}
      <Card className="card-pad">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <Ring value={d.final.conviction} label="conviction" color="#4f46e5" size={84} />
            <div>
              <div className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-[var(--accent-bright)]">
                <Sparkles size={13} /> AI Final Decision
              </div>
              <div className="mt-1 flex items-center gap-2">
                <SignalBadge label={d.final.label} size="lg" />
                <span className="text-sm text-[var(--ink-muted)]">final conf {d.final.final_confidence}%</span>
              </div>
            </div>
          </div>
          <span className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium ${ag.badge}`}>
            {ag.icon}{ag.label}
          </span>
        </div>

        <p className="mt-4 text-sm leading-relaxed text-[var(--ink-secondary)]">{debate.verdict}</p>

        {debate.key_risks.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2">
            {debate.key_risks.map((r, i) => (
              <span key={i} className="inline-flex items-center gap-1 rounded-md bg-[var(--warn-dim)] px-2.5 py-1 text-xs text-amber-700">
                <AlertTriangle size={12} /> {r}
              </span>
            ))}
          </div>
        )}
        <div className="mt-3 text-[10px] uppercase tracking-wide text-slate-400">
          {debate.source === "openrouter" ? "Reasoned by AI agents" : "Deterministic fallback (no LLM)"}
        </div>
      </Card>

      {/* Bull vs Bear */}
      <div className="grid gap-4 md:grid-cols-2">
        <AgentCard tone="bull" title="Bull Analyst" text={debate.bull} icon={<TrendingUp size={15} />} />
        <AgentCard tone="bear" title="Bear Analyst" text={debate.bear} icon={<TrendingDown size={15} />} />
      </div>
    </div>
  );
}

function AgentCard({ tone, title, text, icon }: { tone: "bull" | "bear"; title: string; text: string; icon: React.ReactNode }) {
  const accent = tone === "bull" ? "text-[var(--profit)]" : "text-[var(--loss)]";
  const bar = tone === "bull" ? "bg-[var(--profit-dim)]0" : "bg-[var(--loss-dim)]0";
  return (
    <Card className="relative overflow-hidden card-pad">
      <div className={`absolute left-0 top-0 h-full w-1 ${bar}`} />
      <div className="mb-2 flex items-center gap-2">
        <span className={accent}>{icon}</span>
        <span className={`text-sm font-semibold ${accent}`}>{title}</span>
      </div>
      <p className="text-sm leading-relaxed text-[var(--ink-secondary)]">{text}</p>
    </Card>
  );
}
