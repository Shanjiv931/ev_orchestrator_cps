import { useEffect, useRef, useState } from "react";
import { MapContainer, TileLayer, CircleMarker, Popup, Polyline, useMap } from "react-leaflet";
import { motion, AnimatePresence } from "framer-motion";
import {
  NavigationArrowIcon, LightningIcon, XIcon, ClockIcon, RulerIcon, CarIcon,
  BatteryChargingIcon, BatteryWarningIcon, MapPinIcon, CheckCircleIcon,
  CurrencyInrIcon, PlugsIcon,
} from "@phosphor-icons/react";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import type { Station, Vehicle, VehicleLiveTelemetry } from "../api/types";
import { fetchRoute, haversineKm, type RouteResult } from "../lib/routing";
import { safetyColor } from "../lib/format";
import { GlassCard } from "../components/ui/GlassCard";
import { Button } from "../components/ui/Button";

type ChargerType = "AC" | "DC";
type Phase = "idle" | "choosing-power" | "navigating" | "arrived" | "charging" | "complete";

// Representative power used only for the pre-selection time/cost estimate
// shown while choosing AC vs DC - the actual charger assigned on arrival may
// differ slightly, but this is what lets the user compare before committing.
const REPRESENTATIVE_POWER_KW: Record<ChargerType, number> = { AC: 7.4, DC: 60 };
// INR/kWh - DC fast charging commands a premium over slow AC top-ups, same
// spread used across most Indian public charging networks.
const RATE_PER_KWH: Record<ChargerType, number> = { AC: 8, DC: 18 };
const DEFAULT_BATTERY_CAPACITY_KWH = 40;
const LOW_BATTERY_THRESHOLD_PCT = 10;
const ARRIVAL_RADIUS_KM = 0.1; // 100m
const ROUTE_REFRESH_KM = 0.3; // re-fetch the polyline only after moving this far, to stay within OSRM's fair-use limits

interface RankedStop {
  station: Station;
  score: number;
  distanceKm: number;
  staleHours: number;
  chargerType: ChargerType;
}

interface PowerEstimate {
  type: ChargerType;
  minutesToFull: number;
  costRupees: number;
  stationCount: number;
}

function RecenterOnUser({ lat, lon }: { lat: number; lon: number }) {
  const map = useMap();
  useEffect(() => { map.setView([lat, lon], map.getZoom()); }, [lat, lon, map]);
  return null;
}

export function MapPage() {
  const { user } = useAuth();
  // Vellore, Tamil Nadu - the project's primary implementation city (see
  // lib/indianLocations.ts and backend/app/seed_stations.py). Other cities
  // (Bengaluru, etc.) still exist for users who pick them at onboarding.
  const home: [number, number] = [user?.lat ?? 12.9165, user?.lon ?? 79.1325];

  const [stations, setStations] = useState<Station[]>([]);
  const [myVehicles, setMyVehicles] = useState<Vehicle[]>([]);
  const [selectedVehicleId, setSelectedVehicleId] = useState("");
  const [telemetry, setTelemetry] = useState<VehicleLiveTelemetry | null>(null);

  const [phase, setPhase] = useState<Phase>("idle");
  const [autoTriggered, setAutoTriggered] = useState(false);
  const [estimates, setEstimates] = useState<PowerEstimate[] | null>(null);
  const [ranked, setRanked] = useState<RankedStop[] | null>(null);
  const [activeStop, setActiveStop] = useState<RankedStop | null>(null);
  const [activeRoute, setActiveRoute] = useState<RouteResult | null>(null);
  const [livePos, setLivePos] = useState<[number, number] | null>(null);
  const [liveDistanceKm, setLiveDistanceKm] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [session, setSession] = useState<{ id: string; port_number: number | null } | null>(null);
  const [chargeEnergyKwh, setChargeEnergyKwh] = useState(0);
  const [paidMethod, setPaidMethod] = useState<"upi" | "card" | "cash" | null>(null);
  const [payBusy, setPayBusy] = useState(false);

  const lastRoutedFrom = useRef<[number, number] | null>(null);
  const watchId = useRef<number | null>(null);
  // guards against rapid watchPosition callbacks firing arriveAtStation
  // twice before the "arrived" phase transition re-renders and the effect's
  // phase guard catches up - without it, two start-at-station calls could
  // fire and leave a second charger permanently occupied with no session
  // ever completing it
  const arrivalInFlight = useRef(false);

  const vehicle = myVehicles.find((v) => v.id === selectedVehicleId) ?? null;
  const originPos = livePos ?? home;
  const batteryPct = telemetry?.battery_pct ?? 60;

  useEffect(() => {
    api.get<Station[]>("/stations").then(setStations).catch(() => setStations([]));
    api.get<Vehicle[]>("/vehicles").then((vs) => {
      setMyVehicles(vs);
      if (vs.length > 0) setSelectedVehicleId(vs[0].id);
    }).catch(() => setMyVehicles([]));
  }, []);

  // live battery telemetry for the selected (paired) vehicle - also what
  // drives the auto-trigger-under-10% behaviour below
  useEffect(() => {
    if (!vehicle?.is_paired) { setTelemetry(null); return; }
    let cancelled = false;
    async function poll() {
      try {
        const t = await api.get<VehicleLiveTelemetry>(`/vehicles/${vehicle!.id}/live-telemetry`);
        if (!cancelled) setTelemetry(t);
      } catch { /* ignore - keep last known reading */ }
    }
    poll();
    const interval = setInterval(poll, 10000);
    return () => { cancelled = true; clearInterval(interval); };
  }, [vehicle?.id, vehicle?.is_paired]);

  // point 3: auto-show the best route once battery drops below 10%, using
  // the fastest option (DC) since low battery is by definition urgent
  useEffect(() => {
    if (autoTriggered || phase !== "idle" || !vehicle) return;
    if (telemetry && telemetry.battery_pct < LOW_BATTERY_THRESHOLD_PCT) {
      setAutoTriggered(true);
      void beginFindStation(true);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [telemetry, phase, vehicle, autoTriggered]);

  // browser geolocation - live position while navigating to a station.
  // Denied/unavailable permission just falls back to the home location, so
  // the flow still works (distance/ETA simply won't update en route).
  useEffect(() => {
    if (phase !== "navigating" || !("geolocation" in navigator)) return;
    watchId.current = navigator.geolocation.watchPosition(
      (pos) => setLivePos([pos.coords.latitude, pos.coords.longitude]),
      () => { /* denied or unavailable - stay on home location */ },
      { enableHighAccuracy: true, maximumAge: 5000 },
    );
    return () => {
      if (watchId.current !== null) navigator.geolocation.clearWatch(watchId.current);
      watchId.current = null;
    };
  }, [phase]);

  // recompute the live route + distance as the user's position updates
  useEffect(() => {
    if (phase !== "navigating" || !activeStop) return;
    const distKm = haversineKm(originPos[0], originPos[1], activeStop.station.lat, activeStop.station.lon);
    setLiveDistanceKm(distKm);

    if (distKm <= ARRIVAL_RADIUS_KM) {
      arriveAtStation(activeStop);
      return;
    }

    const from = lastRoutedFrom.current;
    const movedEnough = !from || haversineKm(from[0], from[1], originPos[0], originPos[1]) >= ROUTE_REFRESH_KM;
    if (movedEnough) {
      lastRoutedFrom.current = originPos;
      fetchRoute(originPos[0], originPos[1], activeStop.station.lat, activeStop.station.lon).then(setActiveRoute);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [originPos, phase, activeStop]);

  // simulated live charging ramp - no real charger hardware exists to
  // report actual energy delivered, so this stands in for it while a
  // session is open, and is what gets persisted on completion
  useEffect(() => {
    if (phase !== "charging" || !session) return;
    const capacity = vehicle?.battery_capacity_kwh ?? DEFAULT_BATTERY_CAPACITY_KWH;
    const interval = setInterval(() => {
      setChargeEnergyKwh((kwh) => Math.min(kwh + capacity * 0.02, capacity));
    }, 1000);
    return () => clearInterval(interval);
  }, [phase, session, vehicle?.battery_capacity_kwh]);

  function estimateFor(type: ChargerType): PowerEstimate {
    const capacity = vehicle?.battery_capacity_kwh ?? DEFAULT_BATTERY_CAPACITY_KWH;
    const energyNeeded = Math.max(capacity * (1 - batteryPct / 100), 0.5);
    const power = REPRESENTATIVE_POWER_KW[type];
    const stationCount = stations.filter((s) => s.chargers.some((c) => c.charger_type === type)).length;
    return {
      type,
      minutesToFull: (energyNeeded / power) * 60,
      costRupees: energyNeeded * RATE_PER_KWH[type],
      stationCount,
    };
  }

  async function beginFindStation(auto = false) {
    if (!vehicle) return;
    setError(null);
    setEstimates([estimateFor("AC"), estimateFor("DC")]);
    setPhase("choosing-power");
    if (auto) await chooseChargerType("DC");
  }

  async function chooseChargerType(type: ChargerType) {
    if (!vehicle) return;
    setBusy(true);
    setError(null);
    try {
      const candidates = stations.flatMap((station) =>
        station.chargers
          .filter((c) => c.charger_type === type)
          .map((charger) => ({
            id: charger.id,
            kind: "charge" as const,
            connector_type: vehicle.connector_type,
            lat: station.lat,
            lon: station.lon,
            predicted_wait_minutes: charger.status === "occupied" ? 15 : 0,
            cost_rupees: RATE_PER_KWH[type] * 10,
            congestion_risk: charger.status === "occupied" ? 0.6 : 0.1,
            last_verified_at: charger.last_verified_at,
            reported_status: charger.status,
            safety_score: station.safety_score,
          })),
      );

      if (candidates.length === 0) {
        setError(`No ${type} chargers found nearby.`);
        setPhase("idle");
        return;
      }

      const results = await api.post<{ candidate_id: string; distance_km: number; staleness_hours: number; score: number }[]>(
        "/recommendations",
        {
          vehicle: { connector_type: vehicle.connector_type, is_pluggable: vehicle.is_pluggable },
          candidates,
          user_lat: originPos[0],
          user_lon: originPos[1],
          is_solo_traveler: batteryPct < LOW_BATTERY_THRESHOLD_PCT,
        },
      );

      const byChargerId = new Map(stations.flatMap((s) => s.chargers.map((c) => [c.id, s])));
      const stops: RankedStop[] = results.map((r) => ({
        station: byChargerId.get(r.candidate_id)!,
        score: r.score,
        distanceKm: r.distance_km,
        staleHours: r.staleness_hours,
        chargerType: type,
      })).filter((s) => s.station);

      const seen = new Set<string>();
      const uniqueStops = stops.filter((s) => {
        if (seen.has(s.station.id)) return false;
        seen.add(s.station.id);
        return true;
      });

      if (uniqueStops.length === 0) {
        setError(`No ${type} chargers found nearby.`);
        setPhase("idle");
        return;
      }

      setRanked(uniqueStops.slice(0, 5));
      await selectStop(uniqueStops[0]);
    } finally {
      setBusy(false);
    }
  }

  async function selectStop(stop: RankedStop) {
    setActiveStop(stop);
    lastRoutedFrom.current = originPos;
    const route = await fetchRoute(originPos[0], originPos[1], stop.station.lat, stop.station.lon);
    setActiveRoute(route);
    setLiveDistanceKm(haversineKm(originPos[0], originPos[1], stop.station.lat, stop.station.lon));
    setPhase("navigating");
  }

  async function arriveAtStation(stop: RankedStop) {
    if (!vehicle || phase !== "navigating" || arrivalInFlight.current) return;
    arrivalInFlight.current = true;
    setPhase("arrived");
    try {
      const started = await api.post<{ id: string; port_number: number | null }>("/sessions/start-at-station", {
        vehicle_id: vehicle.id,
        station_id: stop.station.id,
      });
      setSession(started);
      setChargeEnergyKwh(0);
      setPhase("charging");
    } catch {
      setError("No available charger at this station right now - try a nearby port or wait a moment.");
      setPhase("navigating");
    } finally {
      arrivalInFlight.current = false;
    }
  }

  async function stopCharging() {
    if (!session || !activeStop) return;
    setBusy(true);
    try {
      const cost = chargeEnergyKwh * RATE_PER_KWH[activeStop.chargerType];
      await api.patch(`/sessions/${session.id}`, {
        energy_kwh: Number(chargeEnergyKwh.toFixed(2)), cost: Number(cost.toFixed(2)),
      });
      await api.post(`/sessions/${session.id}/complete`);
      setPhase("complete");
    } finally {
      setBusy(false);
    }
  }

  function reset() {
    setPhase("idle");
    setAutoTriggered(false);
    setEstimates(null);
    setRanked(null);
    setActiveStop(null);
    setActiveRoute(null);
    setLiveDistanceKm(null);
    setSession(null);
    setChargeEnergyKwh(0);
    setPaidMethod(null);
    setError(null);
    lastRoutedFrom.current = null;
    arrivalInFlight.current = false;
  }

  async function payAtStation(method: "upi" | "card" | "cash") {
    if (!session) return;
    setPayBusy(true);
    try {
      await api.post(`/payments/sessions/${session.id}/pay`, { method });
      setPaidMethod(method);
    } finally {
      setPayBusy(false);
    }
  }

  const mapCenter = activeStop && phase !== "idle" && phase !== "choosing-power" ? originPos : home;

  return (
    <div className="relative h-[calc(100dvh-9.5rem)] rounded-2xl overflow-hidden glass-panel">
      <MapContainer center={mapCenter} zoom={13} className="w-full h-full" zoomControl={false}>
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <RecenterOnUser lat={mapCenter[0]} lon={mapCenter[1]} />

        {/* the user themselves - always a red dot, per the product's own request */}
        <CircleMarker center={originPos} radius={9} pathOptions={{ color: "#ef4444", fillColor: "#ef4444", fillOpacity: 0.9, weight: 2 }}>
          <Popup>You are here{livePos ? "" : " (home location - live GPS unavailable)"}</Popup>
        </CircleMarker>

        {stations.map((station) => (
          <CircleMarker key={station.id} center={[station.lat, station.lon]} radius={9}
                        pathOptions={{ color: safetyColor(station.safety_score), fillOpacity: 0.7 }}>
            <Popup>
              <strong>{station.station_type}</strong><br />
              Safety: {(station.safety_score * 100).toFixed(0)}%<br />
              Chargers: {station.chargers.length} ({station.chargers.filter((c) => c.charger_type === "DC").length} DC / {station.chargers.filter((c) => c.charger_type === "AC").length} AC)
              &middot; Swap slots: {station.swap_slots.length}
            </Popup>
          </CircleMarker>
        ))}

        {activeRoute && (
          <Polyline positions={activeRoute.coordinates} pathOptions={{ color: "#22d3ee", weight: 5, opacity: 0.85 }} />
        )}
      </MapContainer>

      {/* --- top panel: vehicle select + find-station button / low battery banner --- */}
      <div className="absolute top-3 left-3 right-3 z-[400] flex flex-col gap-2 sm:max-w-sm">
        {telemetry && telemetry.battery_pct < LOW_BATTERY_THRESHOLD_PCT && phase !== "idle" && (
          <GlassCard className="p-3 border-red-400/40 bg-red-500/10">
            <p className="text-xs text-red-300 flex items-center gap-1.5">
              <BatteryWarningIcon size={16} weight="fill" /> Battery critical ({telemetry.battery_pct.toFixed(0)}%) - routing you to the fastest charger.
            </p>
          </GlassCard>
        )}

        {phase === "idle" && myVehicles.length > 0 && (
          <GlassCard className="p-3">
            <div className="flex items-center gap-2 mb-3">
              <CarIcon size={16} className="text-slate-400" />
              <select value={selectedVehicleId} onChange={(e) => setSelectedVehicleId(e.target.value)}
                      className="bg-transparent text-xs flex-1 outline-none cursor-pointer">
                {myVehicles.map((v) => (
                  <option key={v.id} value={v.id} className="bg-slate-900">
                    {v.brand ? `${v.brand} ${v.vehicle_model}` : `${v.vehicle_class} · ${v.connector_type}`}
                  </option>
                ))}
              </select>
              {telemetry && (
                <span className="text-xs text-slate-400 flex items-center gap-1 shrink-0">
                  <BatteryChargingIcon size={14} /> {telemetry.battery_pct.toFixed(0)}%
                </span>
              )}
            </div>
            <Button fullWidth onClick={() => beginFindStation(false)} disabled={busy}>
              <NavigationArrowIcon size={16} weight="fill" />
              Find best station to charge
            </Button>
          </GlassCard>
        )}

        {error && (
          <GlassCard className="p-3 border-red-400/40 bg-red-500/10">
            <p className="text-xs text-red-300">{error}</p>
          </GlassCard>
        )}
      </div>

      {/* --- AC/DC choice sheet --- */}
      <AnimatePresence>
        {phase === "choosing-power" && estimates && (
          <motion.div
            initial={{ y: "100%" }} animate={{ y: 0 }} exit={{ y: "100%" }}
            transition={{ type: "spring", stiffness: 300, damping: 32 }}
            className="absolute bottom-0 inset-x-0 z-[400] glass-panel rounded-t-2xl p-4"
          >
            <div className="flex items-center justify-between mb-3">
              <p className="text-sm font-medium">Charge with AC or DC?</p>
              <button onClick={reset} className="cursor-pointer text-slate-400 hover:text-slate-200">
                <XIcon size={18} />
              </button>
            </div>
            <div className="grid grid-cols-2 gap-3">
              {estimates.map((est) => (
                <button key={est.type} disabled={busy || est.stationCount === 0}
                        onClick={() => chooseChargerType(est.type)}
                        className="text-left p-3 rounded-xl border border-white/10 bg-white/[0.03] hover:bg-white/[0.07] cursor-pointer transition-colors disabled:opacity-40 disabled:cursor-not-allowed">
                  <p className="text-sm font-semibold flex items-center gap-1.5">
                    {est.type === "DC" ? <LightningIcon size={16} weight="fill" className="text-cyan-300" /> : <PlugsIcon size={16} className="text-emerald-300" />}
                    {est.type === "DC" ? "DC fast" : "AC"}
                  </p>
                  <p className="text-xs text-slate-400 mt-1.5 flex items-center gap-1">
                    <ClockIcon size={12} /> ~{Math.round(est.minutesToFull)} min to full
                  </p>
                  <p className="text-xs text-slate-400 mt-0.5 flex items-center gap-1">
                    <CurrencyInrIcon size={12} /> ~₹{Math.round(est.costRupees)}
                  </p>
                  <p className="text-[10px] text-slate-500 mt-1">{est.stationCount} station{est.stationCount === 1 ? "" : "s"} nearby</p>
                </button>
              ))}
            </div>
            {busy && <p className="text-xs text-slate-500 mt-3 text-center">Finding the best station...</p>}
          </motion.div>
        )}
      </AnimatePresence>

      {/* --- navigating / arrived --- */}
      <AnimatePresence>
        {(phase === "navigating" || phase === "arrived") && activeStop && (
          <motion.div
            initial={{ y: "100%" }} animate={{ y: 0 }} exit={{ y: "100%" }}
            transition={{ type: "spring", stiffness: 300, damping: 32 }}
            className="absolute bottom-0 inset-x-0 z-[400] glass-panel rounded-t-2xl p-4"
          >
            <div className="flex items-center justify-between mb-2">
              <p className="text-sm font-medium flex items-center gap-1.5">
                <MapPinIcon size={16} className="text-emerald-400" /> {activeStop.station.station_type} &middot; {activeStop.chargerType}
              </p>
              <button onClick={reset} className="cursor-pointer text-slate-400 hover:text-slate-200">
                <XIcon size={18} />
              </button>
            </div>
            <div className="flex items-center gap-4 text-sm text-cyan-300 mb-3">
              <span className="flex items-center gap-1"><RulerIcon size={14} /> {(liveDistanceKm ?? activeStop.distanceKm).toFixed(1)} km</span>
              {activeRoute && <span className="flex items-center gap-1"><ClockIcon size={14} /> {Math.round(activeRoute.durationMinutes)} min</span>}
              {!livePos && <span className="text-[10px] text-amber-400/80">live GPS unavailable - distance is approximate</span>}
            </div>
            {ranked && ranked.length > 1 && (
              <div className="flex gap-1.5 mb-3 overflow-x-auto">
                {ranked.map((stop) => (
                  <button key={stop.station.id} onClick={() => selectStop(stop)}
                          className={`shrink-0 text-xs px-2.5 py-1 rounded-lg border cursor-pointer ${
                            activeStop.station.id === stop.station.id ? "bg-emerald-500/20 border-emerald-400/40 text-emerald-300" : "border-white/10 text-slate-400"
                          }`}>
                    {stop.station.station_type} &middot; {stop.distanceKm.toFixed(1)}km
                  </button>
                ))}
              </div>
            )}
            {phase === "arrived" ? (
              <p className="text-xs text-slate-400 text-center py-1">Checking in at the station...</p>
            ) : (
              <Button fullWidth variant="secondary" onClick={() => arriveAtStation(activeStop)}>
                <CheckCircleIcon size={16} /> I've arrived
              </Button>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {/* --- live charging status --- */}
      <AnimatePresence>
        {phase === "charging" && session && activeStop && (
          <motion.div
            initial={{ y: "100%" }} animate={{ y: 0 }} exit={{ y: "100%" }}
            transition={{ type: "spring", stiffness: 300, damping: 32 }}
            className="absolute bottom-0 inset-x-0 z-[400] glass-panel rounded-t-2xl p-4"
          >
            <div className="flex items-center justify-between mb-2">
              <p className="text-sm font-medium flex items-center gap-1.5">
                <LightningIcon size={16} weight="fill" className="text-emerald-400 animate-pulse" /> Charging
              </p>
              {session.port_number !== null && (
                <span className="text-xs bg-emerald-500/20 text-emerald-300 px-2 py-1 rounded-lg font-medium">
                  Port {session.port_number}
                </span>
              )}
            </div>
            <p className="text-xs text-slate-500 mb-3">{activeStop.station.station_type}</p>
            <div className="grid grid-cols-2 gap-2 mb-3 text-center text-xs">
              <div className="bg-white/5 rounded-lg py-2">
                <p className="text-slate-500">Delivered</p>
                <p className="font-medium">{chargeEnergyKwh.toFixed(1)} kWh</p>
              </div>
              <div className="bg-white/5 rounded-lg py-2">
                <p className="text-slate-500">Est. cost</p>
                <p className="font-medium">₹{Math.round(chargeEnergyKwh * RATE_PER_KWH[activeStop.chargerType])}</p>
              </div>
            </div>
            <Button fullWidth onClick={stopCharging} disabled={busy}>
              {busy ? "Finishing..." : "Stop charging"}
            </Button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* --- session complete --- */}
      <AnimatePresence>
        {phase === "complete" && activeStop && (
          <motion.div
            initial={{ y: "100%" }} animate={{ y: 0 }} exit={{ y: "100%" }}
            transition={{ type: "spring", stiffness: 300, damping: 32 }}
            className="absolute bottom-0 inset-x-0 z-[400] glass-panel rounded-t-2xl p-4 text-center"
          >
            <CheckCircleIcon size={28} weight="fill" className="text-emerald-400 mx-auto mb-2" />
            <p className="text-sm font-medium">Charging complete - {chargeEnergyKwh.toFixed(1)} kWh delivered</p>

            {paidMethod ? (
              <p className="text-xs text-emerald-300 mt-2 mb-3 flex items-center justify-center gap-1">
                <CheckCircleIcon size={14} weight="fill" /> Paid via {paidMethod}
              </p>
            ) : (
              <>
                <p className="text-xs text-slate-400 mt-1 mb-3">
                  Pay at {activeStop.station.station_type}
                  {activeStop.station.id && <span className="font-mono text-slate-500"> (ID: {activeStop.station.id.slice(0, 8)})</span>}?
                </p>
                <div className="grid grid-cols-3 gap-2 mb-3">
                  {(["upi", "card", "cash"] as const).map((method) => (
                    <button key={method} disabled={payBusy} onClick={() => payAtStation(method)}
                            className="py-2.5 rounded-xl border border-white/10 bg-white/[0.03] hover:bg-white/[0.07] cursor-pointer transition-colors disabled:opacity-50 text-xs capitalize">
                      {method}
                    </button>
                  ))}
                </div>
              </>
            )}

            <Button fullWidth variant="secondary" onClick={reset}>Done</Button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
