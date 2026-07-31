import { useEffect, useRef, useState } from "react";
import { HouseLineIcon, PlusIcon, TrashIcon, LightningIcon, CheckCircleIcon } from "@phosphor-icons/react";
import { api } from "../api/client";
import type { ChargingSession, HomeCharger, Vehicle } from "../api/types";
import { GlassCard } from "./ui/GlassCard";
import { Button } from "./ui/Button";
import { Input, Select, FieldLabel } from "./ui/Input";

const DEFAULT_BATTERY_CAPACITY_KWH = 40;

interface ActiveHomeSession {
  session: ChargingSession;
  homeChargerId: string;
  energyKwh: number;
}

export function HomeChargingSection({ vehicles }: { vehicles: Vehicle[] }) {
  const [chargers, setChargers] = useState<HomeCharger[]>([]);
  const [showAdd, setShowAdd] = useState(false);
  const [label, setLabel] = useState("");
  const [powerKw, setPowerKw] = useState("7.4");
  const [vehicleId, setVehicleId] = useState(vehicles[0]?.id ?? "");
  const [active, setActive] = useState<ActiveHomeSession | null>(null);
  const [error, setError] = useState<string | null>(null);
  const rampInterval = useRef<ReturnType<typeof setInterval> | null>(null);

  async function refresh() {
    try {
      const list = await api.get<HomeCharger[]>("/home-chargers");
      setChargers(list);
    } catch {
      setChargers([]);
    }
  }

  useEffect(() => { refresh(); }, []);
  useEffect(() => { if (!vehicleId && vehicles.length > 0) setVehicleId(vehicles[0].id); }, [vehicles, vehicleId]);

  useEffect(() => {
    if (!active) return;
    const vehicle = vehicles.find((v) => v.id === active.session.vehicle_id);
    const capacity = vehicle?.battery_capacity_kwh ?? DEFAULT_BATTERY_CAPACITY_KWH;
    rampInterval.current = setInterval(() => {
      setActive((prev) => (prev ? { ...prev, energyKwh: Math.min(prev.energyKwh + capacity * 0.015, capacity) } : prev));
    }, 1000);
    return () => { if (rampInterval.current) clearInterval(rampInterval.current); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active?.session.id]);

  async function registerCharger() {
    setError(null);
    try {
      await api.post("/home-chargers", { label, power_kw: Number(powerKw) });
      setLabel("");
      setShowAdd(false);
      refresh();
    } catch {
      setError("Could not register - make sure your home location is set (see onboarding).");
    }
  }

  async function removeCharger(id: string) {
    await api.delete(`/home-chargers/${id}`);
    refresh();
  }

  async function startHomeCharging(homeChargerId: string) {
    if (!vehicleId) return;
    setError(null);
    try {
      const session = await api.post<ChargingSession>("/home-chargers/start-session", {
        vehicle_id: vehicleId, home_charger_id: homeChargerId,
      });
      setActive({ session, homeChargerId, energyKwh: 0 });
    } catch {
      setError("Could not start - this charger may already be in use.");
    }
  }

  async function stopHomeCharging() {
    if (!active) return;
    await api.patch(`/sessions/${active.session.id}`, { energy_kwh: Number(active.energyKwh.toFixed(2)) });
    await api.post(`/sessions/${active.session.id}/complete`);
    setActive(null);
  }

  return (
    <div className="mt-8">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <HouseLineIcon size={20} weight="duotone" className="text-cyan-400" />
          <h2 className="font-medium">Home charging</h2>
        </div>
        <Button variant="ghost" onClick={() => setShowAdd((s) => !s)}>
          <PlusIcon size={14} weight="bold" /> Register charger
        </Button>
      </div>

      {error && <p className="text-red-400 text-xs mb-3">{error}</p>}

      {showAdd && (
        <GlassCard className="mb-4">
          <FieldLabel>Label</FieldLabel>
          <Input value={label} onChange={(e) => setLabel(e.target.value)} placeholder="Garage AC charger" className="mb-3" />
          <FieldLabel>Power (kW)</FieldLabel>
          <Input type="number" step="0.1" value={powerKw} onChange={(e) => setPowerKw(e.target.value)} className="mb-3" />
          <p className="text-xs text-slate-500 mb-3">Uses your registered home location automatically.</p>
          <Button fullWidth onClick={registerCharger} disabled={!label.trim()}>Register</Button>
        </GlassCard>
      )}

      {chargers.length === 0 ? (
        <p className="text-sm text-slate-500">No home chargers registered yet.</p>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {chargers.map((c) => {
            const isActiveHere = active?.homeChargerId === c.id;
            return (
              <GlassCard key={c.id}>
                <div className="flex items-start justify-between">
                  <div>
                    <p className="font-medium text-sm">{c.label}</p>
                    <p className="text-xs text-slate-500">{c.power_kw} kW</p>
                  </div>
                  <button onClick={() => removeCharger(c.id)} className="text-red-400 hover:text-red-300 cursor-pointer" aria-label="Remove home charger">
                    <TrashIcon size={14} />
                  </button>
                </div>

                {isActiveHere && active ? (
                  <div className="mt-3">
                    <div className="grid grid-cols-2 gap-2 mb-2 text-center text-xs">
                      <div className="bg-white/5 rounded-lg py-2">
                        <p className="text-slate-500">Delivered</p>
                        <p className="font-medium">{active.energyKwh.toFixed(1)} kWh</p>
                      </div>
                      <div className="bg-white/5 rounded-lg py-2">
                        <p className="text-slate-500">Status</p>
                        <p className="font-medium flex items-center justify-center gap-1 text-emerald-400">
                          <LightningIcon size={12} weight="fill" className="animate-pulse" /> Charging
                        </p>
                      </div>
                    </div>
                    <Button fullWidth variant="secondary" onClick={stopHomeCharging}>Stop charging</Button>
                  </div>
                ) : (
                  <div className="mt-3 flex gap-2">
                    {vehicles.length > 1 && (
                      <Select value={vehicleId} onChange={(e) => setVehicleId(e.target.value)} className="text-xs">
                        {vehicles.map((v) => (
                          <option key={v.id} value={v.id} className="bg-slate-900">
                            {v.brand ? `${v.brand} ${v.vehicle_model}` : v.vehicle_class}
                          </option>
                        ))}
                      </Select>
                    )}
                    <Button fullWidth={vehicles.length <= 1} onClick={() => startHomeCharging(c.id)} disabled={!!active || !vehicleId}>
                      {active ? "Another session active" : "Start charging"}
                    </Button>
                  </div>
                )}
              </GlassCard>
            );
          })}
        </div>
      )}

      {active && (
        <p className="text-xs text-emerald-300 mt-3 flex items-center gap-1">
          <CheckCircleIcon size={12} weight="fill" /> No payment needed for home charging - it's your own charger.
        </p>
      )}
    </div>
  );
}
