import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { MapContainer, TileLayer, CircleMarker, Polyline, useMap } from "react-leaflet";
import { motion, AnimatePresence } from "framer-motion";
import {
  MagnifyingGlassIcon, XIcon, ClockIcon, RulerIcon, LightningIcon, SuitcaseIcon,
} from "@phosphor-icons/react";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import type { Station } from "../api/types";
import { searchPlace, type GeocodeResult } from "../lib/geocoding";
import { fetchRoute, haversineKm, type RouteResult } from "../lib/routing";
import { safetyColor } from "../lib/format";
import { GlassCard } from "../components/ui/GlassCard";
import { Button } from "../components/ui/Button";
import { StationDetailsPanel } from "../components/StationDetailsPanel";
import { ChargingAdvisoryCard } from "../components/ChargingAdvisoryCard";

// A station "counts" as being along the route if it comes within this
// distance of any sampled point on the polyline - loose enough to catch
// stations just off a highway exit, tight enough that "along the route"
// still means something.
const ROUTE_BUFFER_KM = 5;
const ROUTE_SAMPLE_STRIDE = 5; // check every 5th route point - route polylines can have thousands

interface StopCandidate {
  station: Station;
  distanceFromOriginKm: number;
}

function FitToRoute({ coordinates }: { coordinates: [number, number][] }) {
  const map = useMap();
  useEffect(() => {
    if (coordinates.length === 0) return;
    const lats = coordinates.map((c) => c[0]);
    const lons = coordinates.map((c) => c[1]);
    map.fitBounds([[Math.min(...lats), Math.min(...lons)], [Math.max(...lats), Math.max(...lons)]], { padding: [30, 30] });
  }, [coordinates, map]);
  return null;
}

export function TripPlannerPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const origin: [number, number] = [user?.lat ?? 12.9165, user?.lon ?? 79.1325];

  const [stations, setStations] = useState<Station[]>([]);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<GeocodeResult[]>([]);
  const [destination, setDestination] = useState<GeocodeResult | null>(null);
  const [route, setRoute] = useState<RouteResult | null>(null);
  const [stops, setStops] = useState<StopCandidate[] | null>(null);
  const [selectedStation, setSelectedStation] = useState<Station | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const searchTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);
  const searchGeneration = useRef(0);

  useEffect(() => {
    api.get<Station[]>("/stations").then(setStations).catch(() => setStations([]));
  }, []);

  function handleQueryChange(value: string) {
    setQuery(value);
    setDestination(null);
    const generation = ++searchGeneration.current;
    if (searchTimeout.current) clearTimeout(searchTimeout.current);
    searchTimeout.current = setTimeout(async () => {
      const found = await searchPlace(value, origin[0], origin[1]);
      if (searchGeneration.current === generation) setResults(found);
    }, 350);
  }

  async function planTrip(place: GeocodeResult) {
    searchGeneration.current++;
    setDestination(place);
    setQuery(place.displayName);
    setResults([]);
    setBusy(true);
    setError(null);
    setStops(null);
    try {
      const r = await fetchRoute(origin[0], origin[1], place.lat, place.lon);
      if (!r) {
        setError("Could not find a route to that destination.");
        return;
      }
      setRoute(r);

      const sampled = r.coordinates.filter((_, i) => i % ROUTE_SAMPLE_STRIDE === 0);
      const along = stations
        .map((station) => {
          const minDist = Math.min(...sampled.map(([lat, lon]) => haversineKm(lat, lon, station.lat, station.lon)));
          return { station, minDist, distanceFromOriginKm: haversineKm(origin[0], origin[1], station.lat, station.lon) };
        })
        .filter((s) => s.minDist <= ROUTE_BUFFER_KM)
        .sort((a, b) => a.distanceFromOriginKm - b.distanceFromOriginKm)
        .map(({ station, distanceFromOriginKm }) => ({ station, distanceFromOriginKm }));

      setStops(along);
    } finally {
      setBusy(false);
    }
  }

  function reset() {
    setDestination(null);
    setQuery("");
    setResults([]);
    setRoute(null);
    setStops(null);
    setSelectedStation(null);
    setError(null);
  }

  return (
    <div className="pb-4">
      <div className="flex items-center gap-2 mb-4">
        <SuitcaseIcon size={24} weight="duotone" className="text-cyan-400" />
        <h1 className="font-display text-2xl font-bold">Plan a long trip</h1>
      </div>

      <ChargingAdvisoryCard className="mb-4" />

      <GlassCard className="mb-4">
        <div className="relative flex items-center gap-2">
          <MagnifyingGlassIcon size={18} className="text-slate-400 shrink-0" />
          <input
            value={query}
            onChange={(e) => handleQueryChange(e.target.value)}
            placeholder="Where are you headed?"
            className="w-full bg-transparent outline-none text-sm placeholder:text-slate-500"
          />
          {query && (
            <button onClick={reset} className="cursor-pointer text-slate-500 hover:text-slate-300">
              <XIcon size={16} />
            </button>
          )}
        </div>
        <AnimatePresence>
          {results.length > 0 && !destination && (
            <motion.ul initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }}
                       className="mt-2 overflow-hidden">
              {results.map((r, i) => (
                <li key={i}>
                  <button onClick={() => planTrip(r)}
                          className="w-full text-left text-xs text-slate-300 hover:text-cyan-300 py-1.5 px-1 cursor-pointer truncate">
                    {r.displayName}
                  </button>
                </li>
              ))}
            </motion.ul>
          )}
        </AnimatePresence>
        {error && <p className="text-red-400 text-xs mt-2">{error}</p>}
      </GlassCard>

      {busy && <p className="text-sm text-slate-500 text-center py-6">Planning your route...</p>}

      {route && destination && (
        <>
          <GlassCard glow="electric" className="mb-4 flex items-center justify-between flex-wrap gap-2">
            <div className="text-sm">
              <p className="font-medium">{destination.displayName.split(",")[0]}</p>
              <p className="text-xs text-slate-500 flex items-center gap-3 mt-1">
                <span className="flex items-center gap-1"><RulerIcon size={12} /> {route.distanceKm.toFixed(0)} km</span>
                <span className="flex items-center gap-1"><ClockIcon size={12} /> {(route.durationMinutes / 60).toFixed(1)} hr</span>
                <span className="flex items-center gap-1"><LightningIcon size={12} weight="fill" /> {stops?.length ?? 0} stations</span>
              </p>
            </div>
          </GlassCard>

          <div className="h-64 rounded-2xl overflow-hidden glass-panel mb-4">
            <MapContainer center={origin} zoom={9} className="w-full h-full" zoomControl={false}>
              <TileLayer
                attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              />
              <FitToRoute coordinates={route.coordinates} />
              <CircleMarker center={origin} radius={7} pathOptions={{ color: "#00e5ff", fillColor: "#00e5ff", fillOpacity: 0.9 }} />
              <CircleMarker center={[destination.lat, destination.lon]} radius={7}
                            pathOptions={{ color: "#3b82f6", fillColor: "#3b82f6", fillOpacity: 0.9 }} />
              <Polyline positions={route.coordinates} pathOptions={{ color: "#00e5ff", weight: 4, opacity: 0.8 }} />
              {stops?.map(({ station }) => (
                <CircleMarker key={station.id} center={[station.lat, station.lon]} radius={7}
                              pathOptions={{ color: safetyColor(station.safety_score), fillOpacity: 0.8 }}
                              eventHandlers={{ click: () => setSelectedStation(station) }} />
              ))}
            </MapContainer>
          </div>

          <p className="text-sm font-medium mb-2">Stations along your route</p>
          {stops && stops.length === 0 ? (
            <p className="text-sm text-slate-500">No known charging stations near this route yet.</p>
          ) : (
            <div className="flex flex-col gap-2">
              {stops?.map(({ station, distanceFromOriginKm }) => (
                <button key={station.id} onClick={() => setSelectedStation(station)}
                        className="w-full text-left">
                  <GlassCard hoverLift className="flex items-center justify-between gap-3">
                    <div>
                      <p className="text-sm font-medium">{station.station_type.replace(/_/g, " ")}</p>
                      <p className="text-xs text-slate-500">{station.city ?? "Unknown area"}</p>
                    </div>
                    <span className="text-xs text-cyan-300 shrink-0">{distanceFromOriginKm.toFixed(0)} km in</span>
                  </GlassCard>
                </button>
              ))}
            </div>
          )}
        </>
      )}

      {!route && !busy && (
        <GlassCard className="text-center py-8">
          <p className="text-sm text-slate-500 mb-3">Search a destination above to see charging stops along the way.</p>
          <Button variant="ghost" onClick={() => navigate("/home")}>Back to Home</Button>
        </GlassCard>
      )}

      <AnimatePresence>
        {selectedStation && (
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 20 }} className="mt-4">
            <StationDetailsPanel
              station={selectedStation}
              distanceKm={haversineKm(origin[0], origin[1], selectedStation.lat, selectedStation.lon)}
              onClose={() => setSelectedStation(null)}
            />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
