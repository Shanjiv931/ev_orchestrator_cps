import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Cell } from "recharts";
import { api } from "../api/client";
import type { TwinFeederState } from "../api/types";

interface ForecastPoint {
  hour: number;
  predicted_sessions: number;
}

interface StressTestResult {
  feeder_id: string;
  results: { density_multiplier: number; vehicle_count: number; simultaneous_load_kw: number; is_overloaded: boolean }[];
  breaking_point_multiplier: number | null;
  additional_capacity_needed_kw: number;
  recommended_additional_stations: number;
}

export function AdminPage() {
  const { t } = useTranslation();
  const [zones, setZones] = useState<string[]>([]);
  const [selectedZone, setSelectedZone] = useState("");
  const [forecast, setForecast] = useState<ForecastPoint[]>([]);
  const [feeders, setFeeders] = useState<TwinFeederState[]>([]);
  const [stressResult, setStressResult] = useState<StressTestResult | null>(null);
  const [stressBusy, setStressBusy] = useState(false);

  useEffect(() => {
    api.get<string[]>("/demand-forecast/zones").then((zs) => {
      setZones(zs);
      if (zs.length > 0) setSelectedZone(zs[0]);
    });
    api.get<Record<string, TwinFeederState>>("/twin/feeder").then((f) => setFeeders(Object.values(f))).catch(() => setFeeders([]));
    const interval = setInterval(() => {
      api.get<Record<string, TwinFeederState>>("/twin/feeder").then((f) => setFeeders(Object.values(f))).catch(() => {});
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (!selectedZone) return;
    const today = new Date().getDay();
    Promise.all(
      Array.from({ length: 24 }, (_, hour) =>
        api.get<{ predicted_sessions: number }>(
          `/demand-forecast/predict?zone=${selectedZone}&hour=${hour}&day_of_week=${today}`
        ).then((r) => ({ hour, predicted_sessions: r.predicted_sessions }))
      )
    ).then(setForecast);
  }, [selectedZone]);

  async function runStressTest(feeder: TwinFeederState) {
    setStressBusy(true);
    try {
      const result = await api.post<StressTestResult>("/stress-test/sweep", {
        feeder_id: feeder.feeder_id,
        feeder_capacity_kw: feeder.capacity_kw,
        baseline_vehicle_count: 20,
        avg_charger_power_kw: 30.0,
        simultaneous_charge_fraction: 0.5,
        density_multipliers: [1, 2, 3, 4, 5, 6, 8, 10],
      });
      setStressResult(result);
    } finally {
      setStressBusy(false);
    }
  }

  return (
    <div>
      <h1 className="text-2xl font-semibold mb-6">{t("admin.title")}</h1>

      <section className="mb-8">
        <h2 className="font-medium mb-2">{t("admin.demandForecast")}</h2>
        <select value={selectedZone} onChange={(e) => setSelectedZone(e.target.value)}
                className="border rounded-md px-2 py-1 mb-3 dark:bg-slate-900 dark:border-slate-700">
          {zones.map((z) => <option key={z} value={z}>{z}</option>)}
        </select>
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={forecast}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="hour" />
              <YAxis />
              <Tooltip />
              <Bar dataKey="predicted_sessions" fill="#059669" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </section>

      <section className="mb-8">
        <h2 className="font-medium mb-2">{t("admin.gridStress")}</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {feeders.map((f) => (
            <div key={f.feeder_id} className={`border rounded-lg p-3 ${f.is_overloaded ? "border-red-500" : "dark:border-slate-800"}`}>
              <p className="font-medium text-sm">{f.feeder_zone}</p>
              <p className="text-xs text-slate-500">{f.current_load_kw.toFixed(0)} / {f.capacity_kw.toFixed(0)} kW</p>
              <div className="w-full bg-slate-200 dark:bg-slate-800 rounded-full h-2 mt-2">
                <div className={`h-2 rounded-full ${f.is_overloaded ? "bg-red-600" : "bg-emerald-600"}`}
                     style={{ width: `${Math.min(100, f.loading_percent)}%` }} />
              </div>
              {f.is_rural_minigrid && <p className="text-xs text-amber-600 mt-1">Rural mini-grid</p>}
              <button onClick={() => runStressTest(f)} disabled={stressBusy}
                      className="mt-2 text-xs border rounded-md px-2 py-1 dark:border-slate-700 disabled:opacity-50">
                {t("admin.runStressTest")}
              </button>
            </div>
          ))}
        </div>
      </section>

      {stressResult && (
        <section className="border rounded-lg p-4 dark:border-slate-800">
          <h2 className="font-medium mb-2">{t("admin.stressTest")}: {stressResult.feeder_id}</h2>
          <p className="text-sm">
            Breaking point: density x{stressResult.breaking_point_multiplier ?? "n/a"} ·
            Additional capacity needed: {stressResult.additional_capacity_needed_kw.toFixed(0)} kW ·
            Recommended additional stations: <strong>{stressResult.recommended_additional_stations}</strong>
          </p>
          <div className="h-48 mt-3">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={stressResult.results}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="density_multiplier" label={{ value: "density x", position: "insideBottom", offset: -2 }} />
                <YAxis />
                <Tooltip />
                <Bar dataKey="simultaneous_load_kw">
                  {stressResult.results.map((r, i) => (
                    <Cell key={i} fill={r.is_overloaded ? "#dc2626" : "#059669"} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>
      )}
    </div>
  );
}
