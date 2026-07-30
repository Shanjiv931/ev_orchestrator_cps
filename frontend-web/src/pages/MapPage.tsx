import { useEffect, useMemo, useState } from "react";
import { MapContainer, TileLayer, CircleMarker, Popup } from "react-leaflet";
import { useTranslation } from "react-i18next";
import { api, wsUrl } from "../api/client";
import type { Station, TwinEvState } from "../api/types";
import { safetyColor } from "../lib/format";

const BENGALURU_CENTER: [number, number] = [12.9716, 77.5946];

export function MapPage() {
  const { t } = useTranslation();
  const [stations, setStations] = useState<Station[]>([]);
  const [vehicles, setVehicles] = useState<Record<string, TwinEvState>>({});

  useEffect(() => {
    api.get<Station[]>("/stations").then(setStations).catch(() => setStations([]));
  }, []);

  useEffect(() => {
    const socket = new WebSocket(wsUrl("/ws/live"));
    socket.onmessage = (event) => {
      try {
        const envelope = JSON.parse(event.data);
        if (envelope.entity_type === "ev") {
          setVehicles((prev) => ({ ...prev, [envelope.entity_id]: envelope.data }));
        }
      } catch {
        // ignore malformed frames
      }
    };
    return () => socket.close();
  }, []);

  const vehicleList = useMemo(() => Object.values(vehicles), [vehicles]);

  return (
    <div className="h-[75vh] rounded-lg overflow-hidden border border-slate-200 dark:border-slate-800">
      <MapContainer center={BENGALURU_CENTER} zoom={12} className="w-full h-full">
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {stations.map((station) => (
          <CircleMarker
            key={station.id}
            center={[station.lat, station.lon]}
            radius={10}
            pathOptions={{ color: safetyColor(station.safety_score), fillOpacity: 0.7 }}
          >
            <Popup>
              <strong>{station.station_type}</strong>
              <br />
              {t("stations.safety")}: {(station.safety_score * 100).toFixed(0)}%
              <br />
              {t("stations.chargers")}: {station.chargers.length}
              <br />
              {t("stations.swapSlots")}: {station.swap_slots.length}
            </Popup>
          </CircleMarker>
        ))}
        {vehicleList.map((v) => (
          <CircleMarker key={v.vehicle_id} center={[v.lat, v.lon]} radius={3}
                        pathOptions={{ color: "#2563eb", fillOpacity: 0.9 }}>
            <Popup>
              {v.vehicle_class} - {v.battery_pct.toFixed(0)}% - {v.speed_kmh.toFixed(0)} km/h
            </Popup>
          </CircleMarker>
        ))}
      </MapContainer>
    </div>
  );
}
