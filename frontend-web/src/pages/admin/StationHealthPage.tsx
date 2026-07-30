import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { HeartbeatIcon, CubeIcon } from "@phosphor-icons/react";
import { api } from "../../api/client";
import type { Station } from "../../api/types";
import { GlassCard } from "../../components/ui/GlassCard";

function riskColor(score: number): string {
  if (score >= 0.5) return "text-red-400";
  if (score >= 0.2) return "text-amber-400";
  return "text-emerald-400";
}

export function StationHealthPage() {
  const [stations, setStations] = useState<Station[]>([]);

  useEffect(() => {
    api.get<Station[]>("/stations").then(setStations).catch(() => setStations([]));
  }, []);

  return (
    <div>
      <div className="flex items-center gap-2 mb-6">
        <HeartbeatIcon size={24} weight="duotone" className="text-emerald-400" />
        <h1 className="font-display text-2xl font-bold">Station health</h1>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {stations.map((station) => {
          const worstRisk = Math.max(0, ...station.chargers.map((c) => c.maintenance_risk_score));
          const offlineCount = station.chargers.filter((c) => c.status === "offline").length;
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
              <div className="grid grid-cols-3 gap-3 text-sm">
                <div>
                  <p className="text-slate-500 text-xs">Chargers</p>
                  <p>{station.chargers.length}{offlineCount > 0 && <span className="text-red-400"> ({offlineCount} offline)</span>}</p>
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
            </GlassCard>
          );
        })}
      </div>
    </div>
  );
}
