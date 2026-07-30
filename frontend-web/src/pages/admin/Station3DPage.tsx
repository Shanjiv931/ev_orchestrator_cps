import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { ArrowLeftIcon } from "@phosphor-icons/react";
import { api } from "../../api/client";
import type { Station } from "../../api/types";
import { StationScene } from "../../components/3d/StationScene";
import { GlassCard } from "../../components/ui/GlassCard";

export function Station3DPage() {
  const { stationId } = useParams<{ stationId: string }>();
  const [station, setStation] = useState<Station | null>(null);

  useEffect(() => {
    if (!stationId) return;
    api.get<Station>(`/stations/${stationId}`).then(setStation).catch(() => setStation(null));
    const interval = setInterval(() => {
      api.get<Station>(`/stations/${stationId}`).then(setStation).catch(() => {});
    }, 4000);
    return () => clearInterval(interval);
  }, [stationId]);

  if (!station) return <p className="text-slate-500">Loading station...</p>;

  const occupied = station.chargers.filter((c) => c.status === "occupied").length;
  const loadFraction = station.chargers.length > 0 ? occupied / station.chargers.length : 0;

  return (
    <div>
      <Link to="/admin/station-health" className="inline-flex items-center gap-1 text-sm text-slate-400 hover:text-slate-200 mb-4">
        <ArrowLeftIcon size={16} /> Back to station health
      </Link>

      <h1 className="font-display text-2xl font-bold mb-1">{station.station_type}</h1>
      <p className="text-sm text-slate-500 mb-4">
        Real-time visualization - charger status drives the scene below directly from live data, not a canned animation.
      </p>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <GlassCard className="lg:col-span-2 p-0 overflow-hidden h-[420px]">
          <StationScene chargers={station.chargers} loadFraction={loadFraction} />
        </GlassCard>

        <div className="flex flex-col gap-3">
          <GlassCard>
            <p className="text-xs text-slate-500 mb-1">Utilization</p>
            <p className="text-2xl font-display font-bold">{(loadFraction * 100).toFixed(0)}%</p>
            <p className="text-xs text-slate-500 mt-1">{occupied} / {station.chargers.length} chargers occupied</p>
          </GlassCard>
          <GlassCard>
            <p className="text-xs text-slate-500 mb-2">Legend</p>
            <ul className="text-sm space-y-1.5">
              <li className="flex items-center gap-2"><span className="w-2.5 h-2.5 rounded-full bg-emerald-500" /> Available</li>
              <li className="flex items-center gap-2"><span className="w-2.5 h-2.5 rounded-full bg-cyan-400" /> Occupied (energy flowing)</li>
              <li className="flex items-center gap-2"><span className="w-2.5 h-2.5 rounded-full bg-red-500" /> Offline</li>
            </ul>
          </GlassCard>
          <GlassCard>
            <p className="text-xs text-slate-500 mb-1">Safety score</p>
            <p className="text-lg">{(station.safety_score * 100).toFixed(0)}%</p>
          </GlassCard>
        </div>
      </div>
    </div>
  );
}
