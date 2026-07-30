import { useEffect, useState } from "react";
import { BatteryChargingIcon, SunIcon } from "@phosphor-icons/react";
import { api } from "../api/client";
import type { Station } from "../api/types";
import { GlassCard } from "../components/ui/GlassCard";
import { safetyBadgeClasses } from "../lib/format";

export function StationsPage() {
  const [stations, setStations] = useState<Station[]>([]);
  const [filter, setFilter] = useState<string>("all");

  useEffect(() => {
    api.get<Station[]>("/stations").then(setStations).catch(() => setStations([]));
  }, []);

  const types = ["all", ...new Set(stations.map((s) => s.station_type))];
  const visible = filter === "all" ? stations : stations.filter((s) => s.station_type === filter);

  return (
    <div>
      <div className="flex items-center gap-2 mb-4">
        <BatteryChargingIcon size={24} weight="duotone" className="text-emerald-400" />
        <h1 className="font-display text-2xl font-bold">Charging & swap stations</h1>
      </div>

      <div className="flex gap-2 mb-5 flex-wrap">
        {types.map((type) => (
          <button key={type} onClick={() => setFilter(type)}
                  className={`text-xs px-3 py-1.5 rounded-full border cursor-pointer transition-colors ${
                    filter === type ? "bg-emerald-500/20 border-emerald-400/40 text-emerald-300" : "border-white/10 text-slate-400"
                  }`}>
            {type === "all" ? "All" : type.replace(/_/g, " ")}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {visible.map((station) => (
          <GlassCard key={station.id} hoverLift>
            <div className="flex justify-between items-start">
              <h2 className="font-medium capitalize">{station.station_type.replace(/_/g, " ")}</h2>
              <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${safetyBadgeClasses(station.safety_score)}`}>
                {(station.safety_score * 100).toFixed(0)}%
              </span>
            </div>
            <p className="text-sm text-slate-400 mt-1.5">
              Chargers: {station.chargers.length} &middot; Swap slots: {station.swap_slots.length}
            </p>
            {station.has_solar && (
              <p className="text-xs text-amber-400 mt-1.5 flex items-center gap-1">
                <SunIcon size={13} weight="fill" /> Solar-equipped
              </p>
            )}
          </GlassCard>
        ))}
      </div>
    </div>
  );
}
