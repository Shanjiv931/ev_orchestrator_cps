import { useEffect, useMemo, useRef, useState } from "react";
import { MapContainer, TileLayer, CircleMarker, Popup, Polyline, useMap } from "react-leaflet";
import { motion, AnimatePresence } from "framer-motion";
import {
  MagnifyingGlassIcon, NavigationArrowIcon, LightningIcon, XIcon,
  ClockIcon, RulerIcon, CarIcon,
} from "@phosphor-icons/react";
import { api, wsUrl } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import type { Station, TwinEvState, Vehicle } from "../api/types";
import { searchPlace, type GeocodeResult } from "../lib/geocoding";
import { fetchRoute, type RouteResult } from "../lib/routing";
import { safetyColor } from "../lib/format";
import { GlassCard } from "../components/ui/GlassCard";
import { Button } from "../components/ui/Button";

type Urgency = "low" | "normal" | "urgent";

interface RankedStop {
  station: Station;
  score: number;
  distanceKm: number;
  staleHours: number;
}

function RecenterOnUser({ lat, lon }: { lat: number; lon: number }) {
  const map = useMap();
  useEffect(() => { map.setView([lat, lon], map.getZoom()); }, [lat, lon, map]);
  return null;
}

export function MapPage() {
  const { user } = useAuth();
  const center: [number, number] = [user?.lat ?? 12.9716, user?.lon ?? 77.5946];

  const [stations, setStations] = useState<Station[]>([]);
  const [otherVehicles, setOtherVehicles] = useState<Record<string, TwinEvState>>({});
  const [myVehicles, setMyVehicles] = useState<Vehicle[]>([]);
  const [selectedVehicleId, setSelectedVehicleId] = useState("");

  const [destinationQuery, setDestinationQuery] = useState("");
  const [destinationResults, setDestinationResults] = useState<GeocodeResult[]>([]);
  const [destination, setDestination] = useState<GeocodeResult | null>(null);
  const [urgency, setUrgency] = useState<Urgency>("normal");
  const [ranked, setRanked] = useState<RankedStop[] | null>(null);
  const [activeRoute, setActiveRoute] = useState<RouteResult | null>(null);
  const [activeStop, setActiveStop] = useState<RankedStop | null>(null);
  const [busy, setBusy] = useState(false);
  const searchTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);
  const searchGeneration = useRef(0);

  useEffect(() => {
    api.get<Station[]>("/stations").then(setStations).catch(() => setStations([]));
    api.get<Vehicle[]>("/vehicles").then((vs) => {
      setMyVehicles(vs);
      if (vs.length > 0) setSelectedVehicleId(vs[0].id);
    }).catch(() => setMyVehicles([]));
  }, []);

  useEffect(() => {
    const socket = new WebSocket(wsUrl("/ws/live"));
    socket.onmessage = (event) => {
      try {
        const envelope = JSON.parse(event.data);
        if (envelope.entity_type === "ev") {
          setOtherVehicles((prev) => ({ ...prev, [envelope.entity_id]: envelope.data }));
        }
      } catch {
        // ignore malformed frames
      }
    };
    return () => socket.close();
  }, []);

  function handleDestinationInput(value: string) {
    setDestinationQuery(value);
    setDestination(null);
    const generation = ++searchGeneration.current;
    if (searchTimeout.current) clearTimeout(searchTimeout.current);
    searchTimeout.current = setTimeout(async () => {
      const results = await searchPlace(value, center[0], center[1]);
      // a suggestion may have already been picked (or a newer keystroke
      // started another search) while this request was in flight - applying
      // a stale response would silently reopen the dropdown after selection
      if (searchGeneration.current === generation) setDestinationResults(results);
    }, 350);
  }

  function selectDestination(result: GeocodeResult) {
    searchGeneration.current++;
    setDestination(result);
    setDestinationQuery(result.displayName);
    setDestinationResults([]);
  }

  async function findCharging() {
    const vehicle = myVehicles.find((v) => v.id === selectedVehicleId);
    if (!vehicle) return;
    setBusy(true);
    setActiveRoute(null);
    setActiveStop(null);

    const originLat = destination?.lat ?? center[0];
    const originLon = destination?.lon ?? center[1];

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
      })),
    );

    try {
      const results = await api.post<{ candidate_id: string; distance_km: number; staleness_hours: number; score: number }[]>(
        "/recommendations",
        {
          vehicle: { connector_type: vehicle.connector_type, is_pluggable: vehicle.is_pluggable },
          candidates,
          user_lat: originLat,
          user_lon: originLon,
          is_solo_traveler: urgency === "urgent",
        },
      );

      const byChargerId = new Map(stations.flatMap((s) => s.chargers.map((c) => [c.id, s])));
      const stops: RankedStop[] = results.slice(0, 8).map((r) => ({
        station: byChargerId.get(r.candidate_id)!,
        score: r.score,
        distanceKm: r.distance_km,
        staleHours: r.staleness_hours,
      })).filter((s) => s.station);

      // de-duplicate by station (multiple chargers per station can appear)
      const seen = new Set<string>();
      const uniqueStops = stops.filter((s) => {
        if (seen.has(s.station.id)) return false;
        seen.add(s.station.id);
        return true;
      });

      setRanked(uniqueStops);
    } finally {
      setBusy(false);
    }
  }

  async function selectStop(stop: RankedStop) {
    setActiveStop(stop);
    setActiveRoute(null);
    const origin = destination ?? { lat: center[0], lon: center[1] };
    const route = await fetchRoute(origin.lat, origin.lon, stop.station.lat, stop.station.lon);
    setActiveRoute(route);
  }

  const otherVehicleList = useMemo(() => Object.values(otherVehicles), [otherVehicles]);

  return (
    <div className="relative h-[calc(100dvh-9.5rem)] rounded-2xl overflow-hidden glass-panel">
      <MapContainer center={center} zoom={13} className="w-full h-full" zoomControl={false}>
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <RecenterOnUser lat={center[0]} lon={center[1]} />

        {/* the user themselves - always a red dot, per the product's own request */}
        <CircleMarker center={center} radius={9} pathOptions={{ color: "#ef4444", fillColor: "#ef4444", fillOpacity: 0.9, weight: 2 }}>
          <Popup>You are here</Popup>
        </CircleMarker>

        {stations.map((station) => (
          <CircleMarker key={station.id} center={[station.lat, station.lon]} radius={9}
                        pathOptions={{ color: safetyColor(station.safety_score), fillOpacity: 0.7 }}>
            <Popup>
              <strong>{station.station_type}</strong><br />
              Safety: {(station.safety_score * 100).toFixed(0)}%<br />
              Chargers: {station.chargers.length} &middot; Swap slots: {station.swap_slots.length}
            </Popup>
          </CircleMarker>
        ))}

        {otherVehicleList.map((v) => (
          <CircleMarker key={v.vehicle_id} center={[v.lat, v.lon]} radius={3}
                        pathOptions={{ color: "#2563eb", fillOpacity: 0.9 }}>
            <Popup>{v.vehicle_class} - {v.battery_pct.toFixed(0)}% - {v.speed_kmh.toFixed(0)} km/h</Popup>
          </CircleMarker>
        ))}

        {destination && (
          <CircleMarker center={[destination.lat, destination.lon]} radius={8}
                        pathOptions={{ color: "#a855f7", fillColor: "#a855f7", fillOpacity: 0.85 }}>
            <Popup>Destination</Popup>
          </CircleMarker>
        )}

        {activeRoute && (
          <Polyline positions={activeRoute.coordinates} pathOptions={{ color: "#22d3ee", weight: 5, opacity: 0.85 }} />
        )}
      </MapContainer>

      {/* --- floating search / find-charging panel, Google-Maps style --- */}
      <div className="absolute top-3 left-3 right-3 z-[400] flex flex-col gap-2 sm:max-w-sm">
        <GlassCard className="p-3">
          <div className="relative flex items-center gap-2">
            <MagnifyingGlassIcon size={18} className="text-slate-400 shrink-0" />
            <input
              value={destinationQuery}
              onChange={(e) => handleDestinationInput(e.target.value)}
              placeholder="Where are you headed?"
              className="w-full bg-transparent outline-none text-sm placeholder:text-slate-500"
            />
            {destinationQuery && (
              <button onClick={() => { searchGeneration.current++; setDestinationQuery(""); setDestination(null); setDestinationResults([]); }}
                      className="cursor-pointer text-slate-500 hover:text-slate-300">
                <XIcon size={16} />
              </button>
            )}
          </div>
          <AnimatePresence>
            {destinationResults.length > 0 && !destination && (
              <motion.ul initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }}
                         className="mt-2 overflow-hidden">
                {destinationResults.map((r, i) => (
                  <li key={i}>
                    <button onClick={() => selectDestination(r)}
                            className="w-full text-left text-xs text-slate-300 hover:text-emerald-300 py-1.5 px-1 cursor-pointer truncate">
                      {r.displayName}
                    </button>
                  </li>
                ))}
              </motion.ul>
            )}
          </AnimatePresence>
        </GlassCard>

        {myVehicles.length > 0 && (
          <GlassCard className="p-3">
            <div className="flex items-center gap-2 mb-2">
              <CarIcon size={16} className="text-slate-400" />
              <select value={selectedVehicleId} onChange={(e) => setSelectedVehicleId(e.target.value)}
                      className="bg-transparent text-xs flex-1 outline-none cursor-pointer">
                {myVehicles.map((v) => (
                  <option key={v.id} value={v.id} className="bg-slate-900">
                    {v.brand ? `${v.brand} ${v.vehicle_model}` : `${v.vehicle_class} · ${v.connector_type}`}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex gap-1.5 mb-2">
              {(["low", "normal", "urgent"] as Urgency[]).map((u) => (
                <button key={u} onClick={() => setUrgency(u)}
                        className={`flex-1 text-xs py-1.5 rounded-lg border cursor-pointer transition-colors ${
                          urgency === u ? "bg-emerald-500/20 border-emerald-400/40 text-emerald-300" : "border-white/10 text-slate-400"
                        }`}>
                  {u === "urgent" && <LightningIcon size={12} weight="fill" className="inline mr-1" />}
                  {u[0].toUpperCase() + u.slice(1)}
                </button>
              ))}
            </div>
            <Button fullWidth onClick={findCharging} disabled={busy}>
              <NavigationArrowIcon size={16} weight="fill" />
              {busy ? "Finding..." : "Find charging"}
            </Button>
          </GlassCard>
        )}
      </div>

      {/* --- results bottom sheet --- */}
      <AnimatePresence>
        {ranked && (
          <motion.div
            initial={{ y: "100%" }} animate={{ y: 0 }} exit={{ y: "100%" }}
            transition={{ type: "spring", stiffness: 300, damping: 32 }}
            className="absolute bottom-0 inset-x-0 z-[400] glass-panel rounded-t-2xl max-h-[45%] overflow-y-auto"
          >
            <div className="flex items-center justify-between p-3 border-b border-white/10">
              <p className="text-sm font-medium">{ranked.length} stations found</p>
              <button onClick={() => { setRanked(null); setActiveRoute(null); setActiveStop(null); }}
                      className="cursor-pointer text-slate-400 hover:text-slate-200">
                <XIcon size={18} />
              </button>
            </div>
            <ul className="divide-y divide-white/5">
              {ranked.map((stop) => (
                <li key={stop.station.id}>
                  <button onClick={() => selectStop(stop)}
                          className={`w-full text-left p-3 flex items-center justify-between gap-3 cursor-pointer hover:bg-white/[0.03] ${
                            activeStop?.station.id === stop.station.id ? "bg-emerald-500/10" : ""
                          }`}>
                    <div>
                      <p className="text-sm font-medium">{stop.station.station_type}</p>
                      <p className="text-xs text-slate-500 flex items-center gap-2 mt-0.5">
                        <RulerIcon size={12} /> {stop.distanceKm.toFixed(1)} km
                        {stop.staleHours > 6 && <span className="text-amber-400">stale verification</span>}
                      </p>
                    </div>
                    {activeStop?.station.id === stop.station.id && activeRoute && (
                      <div className="text-right text-xs text-cyan-300 shrink-0">
                        <p className="flex items-center gap-1 justify-end"><ClockIcon size={12} /> {Math.round(activeRoute.durationMinutes)} min</p>
                        <p>{activeRoute.distanceKm.toFixed(1)} km</p>
                      </div>
                    )}
                  </button>
                </li>
              ))}
            </ul>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
