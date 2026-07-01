type Props = {
  label: string;
  value: number | null;
};

// Centered bar: 0 in the middle, negative left (red), positive right (emerald).
export function FactorBar({ label, value }: Props) {
  const available = value !== null && value !== undefined;
  const v = available ? Math.max(-100, Math.min(100, value as number)) : 0;
  const widthPct = Math.abs(v) / 2; // half-track is 50%, so /2 maps 100 -> 50%
  const positive = v >= 0;

  return (
    <div className="flex items-center gap-3 py-1">
      <div className="w-24 shrink-0 text-xs font-medium capitalize text-slate-600">{label}</div>
      <div className="relative h-2.5 flex-1 rounded-full bg-slate-100">
        <div className="absolute left-1/2 top-0 h-full w-px bg-slate-300" />
        {available && (
          <div
            className={`absolute top-0 h-full rounded-full ${positive ? "bg-emerald-500" : "bg-rose-500"}`}
            style={
              positive
                ? { left: "50%", width: `${widthPct}%` }
                : { right: "50%", width: `${widthPct}%` }
            }
          />
        )}
      </div>
      <div className={`w-12 shrink-0 text-right text-xs tabular-nums ${available ? "text-slate-700" : "text-slate-300"}`}>
        {available ? (v > 0 ? `+${Math.round(v)}` : Math.round(v)) : "n/a"}
      </div>
    </div>
  );
}
