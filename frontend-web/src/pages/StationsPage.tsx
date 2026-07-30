import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../api/client";
import type { Station, Vehicle } from "../api/types";
import { isStaleVerification } from "../lib/format";

interface RankedResult {
  candidate_id: string;
  distance_km: number;
  staleness_hours: number;
  score: number;
}

export function StationsPage() {
  const { t } = useTranslation();
  const [stations, setStations] = useState<Station[]>([]);
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [selectedVehicleId, setSelectedVehicleId] = useState<string>("");
  const [isSolo, setIsSolo] = useState(false);
  const [ranked, setRanked] = useState<RankedResult[] | null>(null);

  useEffect(() => {
    api.get<Station[]>("/stations").then(setStations).catch(() => setStations([]));
    api.get<Vehicle[]>("/vehicles").then((vs) => {
      setVehicles(vs);
      if (vs.length > 0) setSelectedVehicleId(vs[0].id);
    }).catch(() => setVehicles([]));
  }, []);

  async function findBestStation() {
    const vehicle = vehicles.find((v) => v.id === selectedVehicleId);
    if (!vehicle) return;

    const candidates = stations.flatMap((station) =>
      station.chargers.map((charger) => ({
        id: charger.id,
        kind: "charge" as const,
        connector_type: vehicle.connector_type,
        lat: station.lat,
        lon: station.lon,
        predicted_wait_minutes: charger.status === "occupied" ? 15 : 0,
        cost_rupees: 20,
        congestion_risk: charger.status === "occupied" ? 0.6 : 0.1,
        last_verified_at: charger.last_verified_at,
        reported_status: charger.status,
        safety_score: station.safety_score,
      }))
    );

    const results = await api.post<RankedResult[]>("/recommendations", {
      vehicle: { connector_type: vehicle.connector_type, is_pluggable: vehicle.is_pluggable },
      candidates,
      user_lat: 12.9716,
      user_lon: 77.5946,
      hour_of_day: new Date().getHours(),
      is_solo_traveler: isSolo,
    });
    setRanked(results);
  }

  return (
    <div>
      <h1 className="text-2xl font-semibold mb-4">{t("stations.title")}</h1>

      {vehicles.length > 0 && (
        <div className="flex flex-wrap items-center gap-3 mb-6 bg-slate-100 dark:bg-slate-900 p-3 rounded-lg">
          <select value={selectedVehicleId} onChange={(e) => setSelectedVehicleId(e.target.value)}
                  className="border rounded-md px-2 py-1 dark:bg-slate-800 dark:border-slate-700">
            {vehicles.map((v) => (
              <option key={v.id} value={v.id}>{v.vehicle_class} - {v.connector_type}</option>
            ))}
          </select>
          <label className="flex items-center gap-1 text-sm">
            <input type="checkbox" checked={isSolo} onChange={(e) => setIsSolo(e.target.checked)} />
            {t("stations.solo")}
          </label>
          <button onClick={findBestStation} className="bg-emerald-600 text-white rounded-md px-3 py-1.5 text-sm">
            {t("stations.recommend")}
          </button>
        </div>
      )}

      {ranked && (
        <div className="mb-6">
          {ranked.length === 0 ? (
            <p className="text-sm text-slate-500">{t("stations.noResults")}</p>
          ) : (
            <ol className="list-decimal list-inside text-sm space-y-1">
              {ranked.map((r) => (
                <li key={r.candidate_id}>
                  {t("stations.distanceKm", { km: r.distance_km.toFixed(1) })} - score {r.score.toFixed(1)}
                  {isStaleVerification(r.staleness_hours) && <span className="text-amber-600"> (stale verification)</span>}
                </li>
              ))}
            </ol>
          )}
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {stations.map((station) => (
          <div key={station.id} className="border rounded-lg p-4 dark:border-slate-800">
            <div className="flex justify-between items-start">
              <h2 className="font-medium">{station.station_type}</h2>
              <span className="text-xs px-2 py-0.5 rounded-full"
                    style={{ background: station.safety_score >= 0.7 ? "#dcfce7" : "#fef3c7" }}>
                {t("stations.safety")}: {(station.safety_score * 100).toFixed(0)}%
              </span>
            </div>
            <p className="text-sm text-slate-500 mt-1">
              {t("stations.chargers")}: {station.chargers.length} · {t("stations.swapSlots")}: {station.swap_slots.length}
            </p>
            {station.has_solar && <p className="text-xs text-amber-600 mt-1">☀ Solar-equipped</p>}
          </div>
        ))}
      </div>
    </div>
  );
}
