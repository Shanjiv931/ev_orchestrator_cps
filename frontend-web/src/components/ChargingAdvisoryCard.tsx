import { useEffect, useState } from "react";
import { CloudSunIcon, CheckCircleIcon, WarningIcon, XCircleIcon } from "@phosphor-icons/react";
import { api } from "../api/client";
import type { ChargingAdvisory } from "../api/types";
import { GlassCard } from "./ui/GlassCard";

const LEVEL_STYLE = {
  good: { icon: CheckCircleIcon, color: "text-emerald-400", border: "border-emerald-400/30", label: "Good time to charge" },
  fair: { icon: WarningIcon, color: "text-amber-400", border: "border-amber-400/30", label: "Fair time to charge" },
  poor: { icon: XCircleIcon, color: "text-red-400", border: "border-red-400/30", label: "Not the best time to charge" },
} as const;

// Real weather (backend/app/services/weather_service.py, Open-Meteo) + live
// grid load + time-of-day tariff, combined into one explainable
// recommendation - see backend/app/services/charging_advisor.py.
export function ChargingAdvisoryCard({ className }: { className?: string }) {
  const [advisory, setAdvisory] = useState<ChargingAdvisory | null>(null);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api.get<ChargingAdvisory>("/weather/advisory").then((a) => { if (!cancelled) setAdvisory(a); }).catch(() => {});
    return () => { cancelled = true; };
  }, []);

  if (!advisory) return null;
  const style = LEVEL_STYLE[advisory.level];
  const Icon = style.icon;

  return (
    <GlassCard className={className} hoverLift>
      <button onClick={() => setExpanded((e) => !e)} className={`w-full flex items-center gap-2.5 text-left cursor-pointer`}>
        <Icon size={18} weight="fill" className={style.color} />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium">{style.label}</p>
          <p className="text-xs text-slate-400 flex items-center gap-1">
            <CloudSunIcon size={12} /> {advisory.temperature_c.toFixed(0)}C in Vellore
          </p>
        </div>
      </button>
      {expanded && (
        <ul className="mt-3 space-y-1.5 border-t border-white/[0.06] pt-3">
          {advisory.reasons.map((reason, i) => (
            <li key={i} className="text-xs text-slate-300 leading-relaxed">- {reason}</li>
          ))}
        </ul>
      )}
    </GlassCard>
  );
}
