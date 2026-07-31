import { useEffect, useState } from "react";
import { CarIcon, BatteryChargingIcon, MapPinLineIcon } from "@phosphor-icons/react";
import { api } from "../../api/client";
import type { CrossDistrictCharging, VelloreFleetVehicle } from "../../api/types";
import { GlassCard } from "../../components/ui/GlassCard";
import { Input } from "../../components/ui/Input";

function batteryColor(pct: number | null): string {
  if (pct === null) return "text-slate-500";
  if (pct >= 50) return "text-emerald-400";
  if (pct >= 20) return "text-amber-400";
  return "text-red-400";
}

export function AdminFleetPage() {
  const [fleet, setFleet] = useState<VelloreFleetVehicle[]>([]);
  const [crossDistrict, setCrossDistrict] = useState<CrossDistrictCharging[]>([]);
  const [query, setQuery] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      api.get<VelloreFleetVehicle[]>("/admin/vellore-fleet"),
      api.get<CrossDistrictCharging[]>("/admin/cross-district-charging"),
    ]).then(([f, c]) => { setFleet(f); setCrossDistrict(c); }).catch(() => setError("You need admin access to view this page."));
  }, []);

  const filtered = fleet.filter((v) => {
    const q = query.trim().toLowerCase();
    if (!q) return true;
    return [v.number_plate, v.owner_name, v.brand, v.vehicle_model, v.owner_profession]
      .some((field) => field?.toLowerCase().includes(q));
  });

  return (
    <div>
      <div className="flex items-center gap-2 mb-6">
        <CarIcon size={24} weight="duotone" className="text-emerald-400" />
        <h1 className="font-display text-2xl font-bold">Vellore fleet</h1>
      </div>

      {error && <p className="text-red-400 text-sm">{error}</p>}

      {!error && (
        <>
          <Input value={query} onChange={(e) => setQuery(e.target.value)}
                 placeholder="Search plate, owner, profession, model..." className="mb-4 max-w-md" />

          <div className="overflow-x-auto rounded-2xl glass-panel mb-8">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-slate-500 uppercase tracking-wide border-b border-white/10">
                  <th className="px-3 py-2.5">Plate</th>
                  <th className="px-3 py-2.5">Vehicle</th>
                  <th className="px-3 py-2.5">Owner</th>
                  <th className="px-3 py-2.5">Profession</th>
                  <th className="px-3 py-2.5">License</th>
                  <th className="px-3 py-2.5">Battery</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {filtered.map((v) => (
                  <tr key={v.vehicle_id} className="hover:bg-white/[0.02]">
                    <td className="px-3 py-2.5 font-mono text-xs">{v.number_plate}</td>
                    <td className="px-3 py-2.5">
                      {v.brand ? `${v.brand} ${v.vehicle_model}` : v.vehicle_class}
                      <span className="text-slate-500 ml-1">({v.vehicle_class})</span>
                    </td>
                    <td className="px-3 py-2.5">{v.owner_name}</td>
                    <td className="px-3 py-2.5 text-slate-400">{v.owner_profession ?? "-"}</td>
                    <td className="px-3 py-2.5 text-slate-400">
                      {v.owner_license_number ?? "-"}
                      {v.owner_license_expiry && (
                        <span className="text-[10px] block text-slate-500">expires {v.owner_license_expiry}</span>
                      )}
                    </td>
                    <td className={`px-3 py-2.5 font-medium flex items-center gap-1 ${batteryColor(v.battery_pct)}`}>
                      {v.battery_pct !== null ? (
                        <>
                          <BatteryChargingIcon size={14} weight={v.is_charging ? "fill" : "regular"} />
                          {v.battery_pct.toFixed(0)}%
                          {v.is_charging && <span className="text-[10px] text-emerald-400 ml-1">charging</span>}
                        </>
                      ) : (
                        <span className="text-slate-500 text-xs">not paired</span>
                      )}
                    </td>
                  </tr>
                ))}
                {filtered.length === 0 && (
                  <tr><td colSpan={6} className="px-3 py-6 text-center text-slate-500">No vehicles match.</td></tr>
                )}
              </tbody>
            </table>
          </div>

          <div className="flex items-center gap-2 mb-3">
            <MapPinLineIcon size={20} weight="duotone" className="text-cyan-400" />
            <h2 className="font-medium">Out-of-Vellore vehicles charging here</h2>
          </div>
          {crossDistrict.length === 0 ? (
            <p className="text-sm text-slate-500">
              None right now - registration is Vellore-plate-only today, so this stays empty until another
              district's vehicles start using Vellore chargers.
            </p>
          ) : (
            <div className="flex flex-col gap-2">
              {crossDistrict.map((c) => (
                <GlassCard key={c.session_id} className="flex items-center justify-between gap-3 flex-wrap">
                  <div className="text-sm">
                    <span className="font-mono text-xs">{c.number_plate}</span> &middot; {c.owner_name}
                  </div>
                  <div className="text-xs text-slate-400">
                    at {c.station_name} &middot; since {new Date(c.session_start_time).toLocaleString()}
                  </div>
                </GlassCard>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
