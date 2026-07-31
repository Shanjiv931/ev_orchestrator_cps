import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Cell } from "recharts";
import { SquaresFourIcon, ArrowsClockwiseIcon } from "@phosphor-icons/react";
import { api } from "../api/client";
import type { TwinFeederState } from "../api/types";
import { GlassCard } from "../components/ui/GlassCard";
import { Button } from "../components/ui/Button";
import { Select } from "../components/ui/Input";

interface ForecastPoint {
  hour: number;
  predicted_sessions: number;
}

interface DemandModelInfo {
  mae: number;
  realDataRows: number;
  syntheticRows: number;
}

interface StressTestResult {
  feeder_id: string;
  results: { density_multiplier: number; vehicle_count: number; simultaneous_load_kw: number; is_overloaded: boolean }[];
  breaking_point_multiplier: number | null;
  additional_capacity_needed_kw: number;
  recommended_additional_stations: number;
}

const CHART_TOOLTIP_STYLE = { background: "#0f1420", border: "1px solid rgba(148,163,184,0.2)", borderRadius: 8, fontSize: 12 };
const AXIS_PROPS = { stroke: "#64748b", tick: { fill: "#94a3b8", fontSize: 11 } };

export function AdminPage() {
  const { t } = useTranslation();
  const [zones, setZones] = useState<string[]>([]);
  const [selectedZone, setSelectedZone] = useState("");
  const [forecast, setForecast] = useState<ForecastPoint[]>([]);
  const [feeders, setFeeders] = useState<TwinFeederState[]>([]);
  const [stressResult, setStressResult] = useState<StressTestResult | null>(null);
  const [stressBusy, setStressBusy] = useState(false);
  const [modelInfo, setModelInfo] = useState<DemandModelInfo | null>(null);
  const [retraining, setRetraining] = useState(false);

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

  async function loadForecast() {
    if (!selectedZone) return;
    const today = new Date().getDay();
    const results = await Promise.all(
      Array.from({ length: 24 }, (_, hour) =>
        api.get<{ predicted_sessions: number; model_mae: number; real_data_rows: number; synthetic_rows: number }>(
          `/demand-forecast/predict?zone=${selectedZone}&hour=${hour}&day_of_week=${today}`
        ).then((r) => ({ hour, predicted_sessions: r.predicted_sessions, meta: r }))
      )
    );
    setForecast(results.map(({ hour, predicted_sessions }) => ({ hour, predicted_sessions })));
    const meta = results[0]?.meta;
    if (meta) setModelInfo({ mae: meta.model_mae, realDataRows: meta.real_data_rows, syntheticRows: meta.synthetic_rows });
  }

  useEffect(() => { loadForecast(); }, [selectedZone]);

  async function retrainModel() {
    setRetraining(true);
    try {
      await api.post("/admin/retrain-demand-model");
      await loadForecast();
    } finally {
      setRetraining(false);
    }
  }

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
      <div className="flex items-center gap-2 mb-6">
        <SquaresFourIcon size={24} weight="duotone" className="text-emerald-400" />
        <h1 className="font-display text-2xl font-bold">{t("admin.title")}</h1>
      </div>

      <GlassCard className="mb-6">
        <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
          <h2 className="font-medium">{t("admin.demandForecast")}</h2>
          <Button variant="ghost" onClick={retrainModel} disabled={retraining} className="!py-1 !px-2.5 text-xs">
            <ArrowsClockwiseIcon size={13} className={retraining ? "animate-spin" : ""} />
            {retraining ? "Retraining..." : "Retrain now"}
          </Button>
        </div>
        {modelInfo && (
          <p className="text-xs text-slate-500 mb-3">
            Trained on {modelInfo.realDataRows} real charging session{modelInfo.realDataRows === 1 ? "" : "s"}
            {" "}+ {modelInfo.syntheticRows} synthetic backfill rows &middot; MAE {modelInfo.mae.toFixed(2)}
          </p>
        )}
        <Select value={selectedZone} onChange={(e) => setSelectedZone(e.target.value)} className="w-auto mb-3">
          {zones.map((z) => <option key={z} value={z} className="bg-slate-900">{z}</option>)}
        </Select>
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={forecast}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.1)" />
              <XAxis dataKey="hour" {...AXIS_PROPS} />
              <YAxis {...AXIS_PROPS} />
              <Tooltip contentStyle={CHART_TOOLTIP_STYLE} />
              <Bar dataKey="predicted_sessions" fill="#10b981" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </GlassCard>

      <div className="mb-6">
        <h2 className="font-medium mb-3">{t("admin.gridStress")}</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {feeders.map((f) => (
            <GlassCard key={f.feeder_id} className={f.is_overloaded ? "border-red-500/50" : ""}>
              <p className="font-medium text-sm">{f.feeder_zone}</p>
              <p className="text-xs text-slate-500">{f.current_load_kw.toFixed(0)} / {f.capacity_kw.toFixed(0)} kW</p>
              <div className="w-full bg-white/10 rounded-full h-2 mt-2">
                <div className={`h-2 rounded-full ${f.is_overloaded ? "bg-red-500" : "bg-emerald-500"}`}
                     style={{ width: `${Math.min(100, f.loading_percent)}%` }} />
              </div>
              {f.is_rural_minigrid && <p className="text-xs text-amber-400 mt-1">Rural mini-grid</p>}
              <Button variant="ghost" onClick={() => runStressTest(f)} disabled={stressBusy} className="mt-2 !py-1 !px-2 text-xs">
                {t("admin.runStressTest")}
              </Button>
            </GlassCard>
          ))}
        </div>
      </div>

      {stressResult && (
        <GlassCard>
          <h2 className="font-medium mb-2">{t("admin.stressTest")}: {stressResult.feeder_id}</h2>
          <p className="text-sm text-slate-400">
            Breaking point: density x{stressResult.breaking_point_multiplier ?? "n/a"} &middot;
            {" "}Additional capacity needed: {stressResult.additional_capacity_needed_kw.toFixed(0)} kW &middot;
            {" "}Recommended additional stations: <strong className="text-slate-200">{stressResult.recommended_additional_stations}</strong>
          </p>
          <div className="h-48 mt-3">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={stressResult.results}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.1)" />
                <XAxis dataKey="density_multiplier" label={{ value: "density x", position: "insideBottom", offset: -2, fill: "#64748b" }} {...AXIS_PROPS} />
                <YAxis {...AXIS_PROPS} />
                <Tooltip contentStyle={CHART_TOOLTIP_STYLE} />
                <Bar dataKey="simultaneous_load_kw">
                  {stressResult.results.map((r, i) => (
                    <Cell key={i} fill={r.is_overloaded ? "#ef4444" : "#10b981"} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </GlassCard>
      )}
    </div>
  );
}
