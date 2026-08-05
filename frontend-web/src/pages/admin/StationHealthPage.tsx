import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { HeartbeatIcon, CubeIcon, PulseIcon, WrenchIcon } from "@phosphor-icons/react";
import { api } from "../../api/client";
import type { Station } from "../../api/types";
import { GlassCard } from "../../components/ui/GlassCard";

const POLL_MS = 6000; // fast enough to visibly track the fault-detection layer's real-time updates

function riskColor(score: number): string {
  if (score >= 0.5) return "text-red-400";
  if (score >= 0.2) return "text-amber-400";
  return "text-emerald-400";
}

// Charger.status flips to "maintenance" the moment the embedded
// fault-detection layer (simulation/charger_monitor_sim.py, applied via
// backend/app/services/fault_consumer.py) reports a sustained critical
// fault - this label/color pairing is what actually surfaces that live.
function statusStyle(status: string): { label: string; color: string } {
  switch (status) {
    case "offline": return { label: "Offline", color: "text-red-400" };
    case "maintenance": return { label: "Fault detected", color: "text-amber-400" };
    case "occupied": return { label: "Charging", color: "text-cyan-300" };
    default: return { label: "Available", color: "text-slate-300" };
  }
}

function verifiedFreshness(lastVerifiedAt: string | null): { label: string; stale: boolean } {
  if (!lastVerifiedAt) return { label: "never verified", stale: true };
  const ageSeconds = (Date.now() - new Date(lastVerifiedAt).getTime()) / 1000;
  const stale = ageSeconds > 15 * 60;
  if (ageSeconds < 60) return { label: `verified ${Math.round(ageSeconds)}s ago`, stale };
  if (ageSeconds < 3600) return { label: `verified ${Math.round(ageSeconds / 60)}m ago`, stale };
  return { label: `verified ${Math.round(ageSeconds / 3600)}h ago`, stale };
}

export function StationHealthPage() {
  const [stations, setStations] = useState<Station[]>([]);

  useEffect(() => {
    let cancelled = false;
    function refresh() {
      api.get<Station[]>("/stations").then((s) => { if (!cancelled) setStations(s); }).catch(() => {});
    }
    refresh();
    const interval = window.setInterval(refresh, POLL_MS);
    return () => { cancelled = true; window.clearInterval(interval); };
  }, []);

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <HeartbeatIcon size={24} weight="duotone" className="text-emerald-400" />
          <h1 className="font-display text-2xl font-bold">Station health</h1>
        </div>
        <span className="text-xs text-slate-400 flex items-center gap-1.5">
          <PulseIcon size={14} className="text-emerald-400 animate-pulse" /> Live, updates every {POLL_MS / 1000}s
        </span>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {stations.map((station) => {
          const worstRisk = Math.max(0, ...station.chargers.map((c) => c.maintenance_risk_score));
          const offlineCount = station.chargers.filter((c) => c.status === "offline").length;
          const maintenanceCount = station.chargers.filter((c) => c.status === "maintenance").length;
          return (
            <GlassCard key={station.id} hoverLift>
              <div className="flex items-center justify-between mb-3">
                <div>
                  <p className="font-medium">{station.station_type}</p>
                  <p className="text-xs text-slate-500">{station.lat.toFixed(3)}, {station.lon.toFixed(3)}</p>
                </div>
                <Link to={`/admin/stations/${station.id}/3d`}
                      className="text-xs flex items-center gap-1 text-cyan-300 hover:text-cyan-200 border border-cyan-400/30 rounded-lg px-2.5 py-1.5">
                  <CubeIcon size={16} weight="duotone" /> 3D view
                </Link>
              </div>
              <div className="grid grid-cols-3 gap-3 text-sm mb-3">
                <div>
                  <p className="text-slate-500 text-xs">Chargers</p>
                  <p>
                    {station.chargers.length}
                    {offlineCount > 0 && <span className="text-red-400"> ({offlineCount} offline)</span>}
                    {maintenanceCount > 0 && <span className="text-amber-400"> ({maintenanceCount} fault)</span>}
                  </p>
                </div>
                <div>
                  <p className="text-slate-500 text-xs">Worst risk score</p>
                  <p className={riskColor(worstRisk)}>{(worstRisk * 100).toFixed(0)}%</p>
                </div>
                <div>
                  <p className="text-slate-500 text-xs">Safety score</p>
                  <p>{(station.safety_score * 100).toFixed(0)}%</p>
                </div>
              </div>

              <div className="space-y-1.5 border-t border-white/[0.06] pt-3">
                {station.chargers.map((charger) => {
                  const status = statusStyle(charger.status);
                  const freshness = verifiedFreshness(charger.last_verified_at);
                  return (
                    <div key={charger.id} className="flex items-center justify-between text-xs">
                      <span className="flex items-center gap-1.5">
                        {charger.status === "maintenance" && <WrenchIcon size={12} className="text-amber-400" />}
                        Port {charger.port_number ?? "-"} &middot; {charger.charger_type}
                      </span>
                      <span className="flex items-center gap-2">
                        <span className={status.color}>{status.label}</span>
                        <span className={freshness.stale ? "text-slate-500" : "text-slate-400"}>{freshness.label}</span>
                      </span>
                    </div>
                  );
                })}
              </div>
            </GlassCard>
          );
        })}
      </div>
    </div>
  );
}
