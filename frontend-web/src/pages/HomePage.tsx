import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  CarIcon, PlusIcon, BatteryChargingIcon, GaugeIcon, LockKeyIcon, LockKeyOpenIcon,
  SpeakerHighIcon, WarningIcon, RoadHorizonIcon, SuitcaseIcon, BriefcaseIcon,
} from "@phosphor-icons/react";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import type { Vehicle, VehicleLiveTelemetry } from "../api/types";
import { GlassCard } from "../components/ui/GlassCard";
import { Button } from "../components/ui/Button";
import { Select } from "../components/ui/Input";

export function HomePage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [selectedVehicleId, setSelectedVehicleId] = useState("");
  const [telemetry, setTelemetry] = useState<VehicleLiveTelemetry | null>(null);
  const [locked, setLocked] = useState(true);
  const [hazardOn, setHazardOn] = useState(false);
  const [hornFlash, setHornFlash] = useState(false);

  useEffect(() => {
    api.get<Vehicle[]>("/vehicles").then((vs) => {
      setVehicles(vs);
      if (vs.length > 0) setSelectedVehicleId(vs[0].id);
    }).catch(() => setVehicles([]));
  }, []);

  const vehicle = vehicles.find((v) => v.id === selectedVehicleId) ?? null;

  useEffect(() => {
    if (!vehicle?.is_paired) { setTelemetry(null); return; }
    let cancelled = false;
    async function poll() {
      try {
        const t = await api.get<VehicleLiveTelemetry>(`/vehicles/${vehicle!.id}/live-telemetry`);
        if (!cancelled) setTelemetry(t);
      } catch { /* ignore */ }
    }
    poll();
    const interval = setInterval(poll, 5000);
    return () => { cancelled = true; clearInterval(interval); };
  }, [vehicle?.id, vehicle?.is_paired]);

  function honk() {
    setHornFlash(true);
    setTimeout(() => setHornFlash(false), 600);
  }

  return (
    <div className="pb-4">
      <h1 className="font-display text-2xl font-bold mb-1">Welcome back, {user?.name?.split(" ")[0]}</h1>
      <p className="text-sm text-slate-500 mb-6">Here's your vehicle and what's next.</p>

      {vehicles.length === 0 ? (
        <GlassCard className="text-center py-10">
          <CarIcon size={32} weight="duotone" className="text-slate-500 mx-auto mb-3" />
          <p className="text-sm text-slate-400 mb-4">No vehicle registered yet.</p>
          <Button onClick={() => navigate("/vehicles")}>
            <PlusIcon size={16} weight="bold" /> Add a vehicle
          </Button>
        </GlassCard>
      ) : (
        <>
          {vehicles.length > 1 && (
            <Select value={selectedVehicleId} onChange={(e) => setSelectedVehicleId(e.target.value)} className="w-auto mb-3">
              {vehicles.map((v) => (
                <option key={v.id} value={v.id} className="bg-slate-900">
                  {v.brand ? `${v.brand} ${v.vehicle_model}` : v.vehicle_class}
                </option>
              ))}
            </Select>
          )}

          {vehicle && (
            <GlassCard glow="brand" className="mb-4">
              <div className="h-56 rounded-xl overflow-hidden bg-white/[0.06] mb-3 flex items-center justify-center relative">
                {telemetry?.is_charging && (
                  <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(16,185,129,0.25),transparent_70%)] animate-pulse" />
                )}
                <img src="/images/car.webp" alt="Your vehicle" className="relative w-full h-full object-contain p-4" />
              </div>
              <h2 className="font-display text-xl font-bold">
                {vehicle.brand ? `${vehicle.brand} ${vehicle.vehicle_model}` : vehicle.vehicle_class}
              </h2>
              {vehicle.number_plate && <p className="text-sm font-mono text-slate-400 mt-0.5">{vehicle.number_plate}</p>}

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mt-4 text-center text-xs">
                <div className="bg-white/5 rounded-lg py-2">
                  <p className="text-slate-500">Class</p>
                  <p className="font-medium mt-0.5">{vehicle.vehicle_class}</p>
                </div>
                <div className="bg-white/5 rounded-lg py-2">
                  <p className="text-slate-500">Connector</p>
                  <p className="font-medium mt-0.5">{vehicle.connector_type}</p>
                </div>
                <div className="bg-white/5 rounded-lg py-2">
                  <p className="text-slate-500">Chemistry</p>
                  <p className="font-medium mt-0.5">{vehicle.battery_chemistry}</p>
                </div>
                <div className="bg-white/5 rounded-lg py-2">
                  <p className="text-slate-500">Capacity</p>
                  <p className="font-medium mt-0.5">{vehicle.battery_capacity_kwh ? `${vehicle.battery_capacity_kwh} kWh` : "-"}</p>
                </div>
              </div>

              {vehicle.is_paired && telemetry ? (
                <>
                  <div className="grid grid-cols-3 gap-2 mt-2 text-center text-xs">
                    <div className="bg-white/5 rounded-lg py-2">
                      <p className="text-slate-500 flex items-center justify-center gap-1"><BatteryChargingIcon size={12} /> Charge</p>
                      <p className="font-medium mt-0.5">{telemetry.battery_pct.toFixed(0)}%</p>
                    </div>
                    <div className="bg-white/5 rounded-lg py-2">
                      <p className="text-slate-500 flex items-center justify-center gap-1"><RoadHorizonIcon size={12} /> Range</p>
                      <p className="font-medium mt-0.5">{telemetry.range_km.toFixed(0)} km</p>
                    </div>
                    <div className="bg-white/5 rounded-lg py-2">
                      <p className="text-slate-500 flex items-center justify-center gap-1"><GaugeIcon size={12} /> Odometer</p>
                      <p className="font-medium mt-0.5">{telemetry.odometer_km.toFixed(0)} km</p>
                    </div>
                  </div>

                  <div className="grid grid-cols-3 gap-2 mt-3">
                    <button onClick={() => setLocked((l) => !l)}
                            className="flex flex-col items-center gap-1 py-2.5 rounded-xl border border-white/10 bg-white/[0.03] hover:bg-white/[0.07] cursor-pointer transition-colors text-[11px]">
                      {locked ? <LockKeyIcon size={18} className="text-emerald-300" /> : <LockKeyOpenIcon size={18} className="text-amber-300" />}
                      {locked ? "Locked" : "Unlocked"}
                    </button>
                    <button onClick={honk}
                            className="flex flex-col items-center gap-1 py-2.5 rounded-xl border border-white/10 bg-white/[0.03] hover:bg-white/[0.07] cursor-pointer transition-colors text-[11px]">
                      <SpeakerHighIcon size={18} weight={hornFlash ? "fill" : "regular"} className={hornFlash ? "text-cyan-300" : "text-slate-300"} />
                      Horn
                    </button>
                    <button onClick={() => setHazardOn((h) => !h)}
                            className="flex flex-col items-center gap-1 py-2.5 rounded-xl border border-white/10 bg-white/[0.03] hover:bg-white/[0.07] cursor-pointer transition-colors text-[11px]">
                      <WarningIcon size={18} weight={hazardOn ? "fill" : "regular"} className={hazardOn ? "text-amber-300" : "text-slate-300"} />
                      Hazard
                    </button>
                  </div>
                  <p className="text-[10px] text-amber-400/80 mt-2 text-center">
                    Simulated controls - no real vehicle connection exists.
                  </p>
                </>
              ) : (
                <p className="text-xs text-slate-500 mt-3 text-center">
                  Pair this vehicle from the Vehicles page to see live status and controls.
                </p>
              )}
            </GlassCard>
          )}
        </>
      )}

      <GlassCard glow="electric">
        <p className="font-medium mb-1">What are you doing today?</p>
        <p className="text-xs text-slate-500 mb-3">We'll tailor charging stops to match.</p>
        <div className="grid grid-cols-2 gap-3">
          <button onClick={() => navigate("/map")}
                  className="flex flex-col items-center gap-2 py-4 rounded-xl border border-white/10 bg-white/[0.03] hover:bg-emerald-500/10 hover:border-emerald-400/30 cursor-pointer transition-colors">
            <BriefcaseIcon size={22} className="text-emerald-300" />
            <span className="text-sm font-medium">Daily use</span>
            <span className="text-[10px] text-slate-500 px-2 text-center">Find the best nearby station</span>
          </button>
          <button onClick={() => navigate("/trip-planner")}
                  className="flex flex-col items-center gap-2 py-4 rounded-xl border border-white/10 bg-white/[0.03] hover:bg-cyan-500/10 hover:border-cyan-400/30 cursor-pointer transition-colors">
            <SuitcaseIcon size={22} className="text-cyan-300" />
            <span className="text-sm font-medium">Long trip</span>
            <span className="text-[10px] text-slate-500 px-2 text-center">Plan a route with charging stops</span>
          </button>
        </div>
      </GlassCard>
    </div>
  );
}
