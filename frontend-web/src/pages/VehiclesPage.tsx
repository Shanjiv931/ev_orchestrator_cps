import { useEffect, useMemo, useState } from "react";
import {
  CarIcon, PlusIcon, LinkIcon, BatteryChargingIcon, SparkleIcon,
} from "@phosphor-icons/react";
import { api } from "../api/client";
import type { BatteryHealth, CatalogEntry, Vehicle, VehicleLiveTelemetry, VehiclePairingResponse } from "../api/types";
import { GlassCard } from "../components/ui/GlassCard";
import { Button } from "../components/ui/Button";
import { Input, Select, FieldLabel } from "../components/ui/Input";
import { CarScene } from "../components/3d/CarScene";

const VEHICLE_CLASSES = ["2W", "3W", "4W"] as const;
// The connector/chemistry enums the rest of the platform (twin, simulation,
// recommendation scorer) actually understands end-to-end - a "manual entry"
// path that accepted arbitrary strings here would silently break matching
// everywhere else, so these stay fixed even though the catalog path below
// offers far more variety at the vehicle-model level.
const CONNECTORS = ["Bharat AC-001", "Bharat DC-001", "CCS2", "Type 2", "swap-cassette"];
const CHEMISTRIES = ["LFP", "NMC", "lead-acid"];

type AddMode = "catalog" | "manual";

export function VehiclesPage() {
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [health, setHealth] = useState<Record<string, BatteryHealth | null>>({});
  const [showForm, setShowForm] = useState(false);
  const [addMode, setAddMode] = useState<AddMode>("catalog");
  const [expandedId, setExpandedId] = useState<string | null>(null);

  // catalog mode
  const [catalog, setCatalog] = useState<CatalogEntry[]>([]);
  const [selectedBrand, setSelectedBrand] = useState("");
  const [selectedModel, setSelectedModel] = useState("");

  // manual mode
  const [vehicleClass, setVehicleClass] = useState<(typeof VEHICLE_CLASSES)[number]>("4W");
  const [connector, setConnector] = useState(CONNECTORS[2]);
  const [chemistry, setChemistry] = useState(CHEMISTRIES[1]);
  const [isPluggable, setIsPluggable] = useState(true);

  const brands = useMemo(() => [...new Set(catalog.map((c) => c.brand))], [catalog]);
  const modelsForBrand = useMemo(() => catalog.filter((c) => c.brand === selectedBrand), [catalog, selectedBrand]);
  const selectedCatalogEntry = useMemo(
    () => modelsForBrand.find((m) => m.vehicle_model === selectedModel),
    [modelsForBrand, selectedModel],
  );

  async function refresh() {
    const vs = await api.get<Vehicle[]>("/vehicles");
    setVehicles(vs);
    for (const v of vs) {
      try {
        const latest = await api.get<BatteryHealth>(`/vehicles/${v.id}/battery-health/latest`);
        setHealth((prev) => ({ ...prev, [v.id]: latest }));
      } catch {
        setHealth((prev) => ({ ...prev, [v.id]: null }));
      }
    }
  }

  useEffect(() => {
    refresh();
    api.get<CatalogEntry[]>("/vehicle-catalog").then((entries) => {
      setCatalog(entries);
      if (entries.length > 0) {
        setSelectedBrand(entries[0].brand);
        setSelectedModel(entries[0].vehicle_model);
      }
    });
  }, []);

  async function addFromCatalog() {
    if (!selectedCatalogEntry) return;
    const e = selectedCatalogEntry;
    await api.post("/vehicles", {
      vehicle_class: e.vehicle_class, connector_type: e.connector_type, battery_chemistry: e.battery_chemistry,
      is_pluggable: e.is_pluggable, brand: e.brand, vehicle_model: e.vehicle_model,
      battery_capacity_kwh: e.battery_capacity_kwh, color_hex: e.color_hex,
    });
    setShowForm(false);
    refresh();
  }

  async function addManual() {
    await api.post("/vehicles", {
      vehicle_class: vehicleClass, connector_type: connector, battery_chemistry: chemistry, is_pluggable: isPluggable,
      color_hex: "#1E293B",
    });
    setShowForm(false);
    refresh();
  }

  return (
    <div className="pb-4">
      <div className="flex justify-between items-center mb-4">
        <div className="flex items-center gap-2">
          <CarIcon size={24} weight="duotone" className="text-emerald-400" />
          <h1 className="font-display text-2xl font-bold">My vehicles</h1>
        </div>
        <Button onClick={() => setShowForm((s) => !s)}>
          <PlusIcon size={16} weight="bold" /> Add vehicle
        </Button>
      </div>

      {showForm && (
        <GlassCard className="mb-6">
          <div className="flex gap-2 mb-4">
            <button onClick={() => setAddMode("catalog")}
                    className={`flex-1 text-sm py-1.5 rounded-lg cursor-pointer transition-colors ${addMode === "catalog" ? "bg-emerald-500/20 text-emerald-300" : "text-slate-400"}`}>
              Choose from catalog
            </button>
            <button onClick={() => setAddMode("manual")}
                    className={`flex-1 text-sm py-1.5 rounded-lg cursor-pointer transition-colors ${addMode === "manual" ? "bg-emerald-500/20 text-emerald-300" : "text-slate-400"}`}>
              Enter manually
            </button>
          </div>

          {addMode === "catalog" ? (
            <div className="flex flex-col gap-3">
              <div>
                <FieldLabel>Brand</FieldLabel>
                <Select value={selectedBrand} onChange={(e) => {
                  setSelectedBrand(e.target.value);
                  const first = catalog.find((c) => c.brand === e.target.value);
                  if (first) setSelectedModel(first.vehicle_model);
                }}>
                  {brands.map((b) => <option key={b} value={b} className="bg-slate-900">{b}</option>)}
                </Select>
              </div>
              <div>
                <FieldLabel>Model</FieldLabel>
                <Select value={selectedModel} onChange={(e) => setSelectedModel(e.target.value)}>
                  {modelsForBrand.map((m) => (
                    <option key={m.vehicle_model} value={m.vehicle_model} className="bg-slate-900">{m.vehicle_model}</option>
                  ))}
                </Select>
              </div>
              {selectedCatalogEntry && (
                <div className="text-xs text-slate-400 bg-white/5 rounded-lg p-3 grid grid-cols-2 gap-1.5">
                  <span>Class: {selectedCatalogEntry.vehicle_class}</span>
                  <span>Connector: {selectedCatalogEntry.connector_type}</span>
                  <span>Chemistry: {selectedCatalogEntry.battery_chemistry}</span>
                  <span>Capacity: {selectedCatalogEntry.battery_capacity_kwh} kWh</span>
                </div>
              )}
              <p className="text-xs text-slate-500">
                Not sure which one? Pick the closest match above from our narrowed Indian EV list.
              </p>
              <Button onClick={addFromCatalog}>Add this vehicle</Button>
            </div>
          ) : (
            <div className="flex flex-col gap-3">
              <div>
                <FieldLabel>Vehicle class</FieldLabel>
                <Select value={vehicleClass} onChange={(e) => setVehicleClass(e.target.value as typeof vehicleClass)}>
                  {VEHICLE_CLASSES.map((c) => <option key={c} value={c} className="bg-slate-900">{c}</option>)}
                </Select>
              </div>
              <div>
                <FieldLabel>Connector type</FieldLabel>
                <Select value={connector} onChange={(e) => setConnector(e.target.value)}>
                  {CONNECTORS.map((c) => <option key={c} value={c} className="bg-slate-900">{c}</option>)}
                </Select>
              </div>
              <div>
                <FieldLabel>Battery chemistry</FieldLabel>
                <Select value={chemistry} onChange={(e) => setChemistry(e.target.value)}>
                  {CHEMISTRIES.map((c) => <option key={c} value={c} className="bg-slate-900">{c}</option>)}
                </Select>
              </div>
              <label className="flex items-center gap-2 text-sm text-slate-300">
                <input type="checkbox" checked={isPluggable} onChange={(e) => setIsPluggable(e.target.checked)} />
                Plug-in capable
              </label>
              <Button onClick={addManual}>Add this vehicle</Button>
            </div>
          )}
        </GlassCard>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {vehicles.map((v) => (
          <VehicleCard key={v.id} vehicle={v} health={health[v.id] ?? null}
                       expanded={expandedId === v.id}
                       onToggle={() => setExpandedId(expandedId === v.id ? null : v.id)}
                       onPaired={refresh} />
        ))}
      </div>
    </div>
  );
}

function VehicleCard({ vehicle, health, expanded, onToggle, onPaired }: {
  vehicle: Vehicle; health: BatteryHealth | null; expanded: boolean; onToggle: () => void; onPaired: () => void;
}) {
  const [pairingCode, setPairingCode] = useState<string | null>(null);
  const [confirmCode, setConfirmCode] = useState("");
  const [telemetry, setTelemetry] = useState<VehicleLiveTelemetry | null>(null);
  const [pairError, setPairError] = useState<string | null>(null);

  useEffect(() => {
    if (!expanded || !vehicle.is_paired) return;
    let cancelled = false;
    async function poll() {
      try {
        const t = await api.get<VehicleLiveTelemetry>(`/vehicles/${vehicle.id}/live-telemetry`);
        if (!cancelled) setTelemetry(t);
      } catch { /* ignore */ }
    }
    poll();
    const interval = setInterval(poll, 5000);
    return () => { cancelled = true; clearInterval(interval); };
  }, [expanded, vehicle.is_paired, vehicle.id]);

  async function startPairing() {
    const response = await api.post<VehiclePairingResponse>(`/vehicles/${vehicle.id}/pair`);
    setPairingCode(response.pairing_code);
    setPairError(null);
  }

  async function confirmPairing() {
    try {
      await api.post(`/vehicles/${vehicle.id}/pair/confirm?code=${encodeURIComponent(confirmCode)}`);
      setPairingCode(null);
      onPaired();
    } catch {
      setPairError("Incorrect code - check the (simulated) in-car display and try again");
    }
  }

  return (
    <GlassCard hoverLift>
      <div className="flex justify-between items-start">
        <div>
          <h2 className="font-medium">{vehicle.brand ? `${vehicle.brand} ${vehicle.vehicle_model}` : vehicle.vehicle_class}</h2>
          <p className="text-sm text-slate-500">{vehicle.connector_type} &middot; {vehicle.battery_chemistry}{!vehicle.is_pluggable && " · non-plug-in hybrid"}</p>
        </div>
        <button onClick={onToggle} className="text-xs text-cyan-300 hover:text-cyan-200 cursor-pointer flex items-center gap-1">
          <SparkleIcon size={14} weight="fill" /> {expanded ? "Hide" : "View"} 3D
        </button>
      </div>

      {health && (
        <div className="mt-2 text-sm space-y-1">
          <p><strong>SoH:</strong> {health.soh_pct.toFixed(1)}%</p>
          {health.projected_months_to_80pct !== null && (
            <p className="text-slate-500">Months to 80% threshold: {health.projected_months_to_80pct.toFixed(0)}</p>
          )}
        </div>
      )}

      {expanded && (
        <div className="mt-3">
          <div className="h-56 rounded-xl overflow-hidden bg-black/20">
            <CarScene
              colorHex={vehicle.color_hex ?? "#1E293B"}
              vehicleClass={vehicle.vehicle_class}
              batteryPct={telemetry?.battery_pct ?? 60}
              isCharging={telemetry?.is_charging ?? false}
            />
          </div>

          {vehicle.is_paired ? (
            telemetry && (
              <div className="grid grid-cols-3 gap-2 mt-3 text-center text-xs">
                <div className="bg-white/5 rounded-lg py-2">
                  <p className="text-slate-500">Charge</p>
                  <p className="font-medium">{telemetry.battery_pct.toFixed(0)}%</p>
                </div>
                <div className="bg-white/5 rounded-lg py-2">
                  <p className="text-slate-500">Range</p>
                  <p className="font-medium">{telemetry.range_km.toFixed(0)} km</p>
                </div>
                <div className="bg-white/5 rounded-lg py-2">
                  <p className="text-slate-500">Status</p>
                  <p className="font-medium">{telemetry.is_charging ? "Charging" : "Idle"}</p>
                </div>
                <p className="col-span-3 text-[10px] text-amber-400/80 mt-1">
                  Simulated telemetry - no real vehicle connection exists.
                </p>
              </div>
            )
          ) : pairingCode ? (
            <div className="mt-3 bg-white/5 rounded-lg p-3">
              <p className="text-xs text-slate-400 mb-2">
                Simulated pairing code (as if shown on your car's display): <strong className="text-emerald-300">{pairingCode}</strong>
              </p>
              <div className="flex gap-2">
                <Input value={confirmCode} onChange={(e) => setConfirmCode(e.target.value)} placeholder="Enter code" className="text-xs" />
                <Button onClick={confirmPairing}>Confirm</Button>
              </div>
              {pairError && <p className="text-red-400 text-xs mt-1">{pairError}</p>}
            </div>
          ) : (
            <Button variant="secondary" fullWidth className="mt-3" onClick={startPairing}>
              <LinkIcon size={16} /> Link vehicle (simulated)
            </Button>
          )}
        </div>
      )}

      {!health && !expanded && (
        <p className="text-xs text-slate-500 mt-2 flex items-center gap-1">
          <BatteryChargingIcon size={14} /> No battery health records yet.
        </p>
      )}
    </GlassCard>
  );
}
