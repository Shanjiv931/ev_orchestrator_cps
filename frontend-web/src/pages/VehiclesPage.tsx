import { useEffect, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../api/client";
import type { BatteryHealth, Vehicle } from "../api/types";

const VEHICLE_CLASSES = ["2W", "3W", "4W"] as const;
const CONNECTORS = ["Bharat AC-001", "Bharat DC-001", "CCS2", "Type 2", "swap-cassette"];
const CHEMISTRIES = ["LFP", "NMC", "lead-acid"];

export function VehiclesPage() {
  const { t } = useTranslation();
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [health, setHealth] = useState<Record<string, BatteryHealth | null>>({});
  const [showForm, setShowForm] = useState(false);
  const [vehicleClass, setVehicleClass] = useState<(typeof VEHICLE_CLASSES)[number]>("4W");
  const [connector, setConnector] = useState(CONNECTORS[2]);
  const [chemistry, setChemistry] = useState(CHEMISTRIES[1]);
  const [isPluggable, setIsPluggable] = useState(true);

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

  useEffect(() => { refresh(); }, []);

  async function handleAdd(e: FormEvent) {
    e.preventDefault();
    await api.post("/vehicles", {
      vehicle_class: vehicleClass, connector_type: connector, battery_chemistry: chemistry, is_pluggable: isPluggable,
    });
    setShowForm(false);
    refresh();
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-4">
        <h1 className="text-2xl font-semibold">{t("vehicles.title")}</h1>
        <button onClick={() => setShowForm((s) => !s)} className="bg-emerald-600 text-white rounded-md px-3 py-1.5 text-sm">
          {t("vehicles.add")}
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleAdd} className="border rounded-lg p-4 mb-6 flex flex-wrap gap-3 items-end dark:border-slate-800">
          <label className="flex flex-col text-sm">
            {t("vehicles.class")}
            <select value={vehicleClass} onChange={(e) => setVehicleClass(e.target.value as typeof vehicleClass)}
                    className="border rounded-md px-2 py-1 dark:bg-slate-900 dark:border-slate-700">
              {VEHICLE_CLASSES.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </label>
          <label className="flex flex-col text-sm">
            {t("vehicles.connector")}
            <select value={connector} onChange={(e) => setConnector(e.target.value)}
                    className="border rounded-md px-2 py-1 dark:bg-slate-900 dark:border-slate-700">
              {CONNECTORS.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </label>
          <label className="flex flex-col text-sm">
            {t("vehicles.chemistry")}
            <select value={chemistry} onChange={(e) => setChemistry(e.target.value)}
                    className="border rounded-md px-2 py-1 dark:bg-slate-900 dark:border-slate-700">
              {CHEMISTRIES.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </label>
          <label className="flex items-center gap-1 text-sm">
            <input type="checkbox" checked={isPluggable} onChange={(e) => setIsPluggable(e.target.checked)} />
            {t("vehicles.pluggable")}
          </label>
          <button type="submit" className="bg-emerald-600 text-white rounded-md px-3 py-1.5 text-sm">{t("common.save")}</button>
        </form>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {vehicles.map((v) => {
          const h = health[v.id];
          return (
            <div key={v.id} className="border rounded-lg p-4 dark:border-slate-800">
              <h2 className="font-medium">{v.vehicle_class} · {v.connector_type}</h2>
              <p className="text-sm text-slate-500">{v.battery_chemistry}{!v.is_pluggable && " · non-plug-in hybrid"}</p>
              {h ? (
                <div className="mt-2 text-sm space-y-1">
                  <p><strong>{t("vehicles.soh")}:</strong> {h.soh_pct.toFixed(1)}%</p>
                  {h.projected_months_to_80pct !== null && (
                    <p className="text-slate-500">{t("vehicles.monthsTo80")}: {h.projected_months_to_80pct.toFixed(0)}</p>
                  )}
                  <p className="text-slate-500">{t("vehicles.trend")}: {h.trend_flag}</p>
                </div>
              ) : (
                <p className="text-xs text-slate-400 mt-2">No battery health records yet.</p>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
