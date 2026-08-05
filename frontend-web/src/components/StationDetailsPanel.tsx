import {
  MapPinIcon, XIcon, ShieldCheckIcon, SunIcon, RulerIcon,
  LightningIcon, PlugsIcon, ArrowsLeftRightIcon, NavigationArrowIcon, HourglassIcon, BookmarkSimpleIcon,
} from "@phosphor-icons/react";
import type { Station } from "../api/types";
import { formatStationType, safetyBadgeClasses } from "../lib/format";
import { RATE_PER_KWH } from "../lib/chargingRates";
import { GlassCard } from "./ui/GlassCard";
import { Button } from "./ui/Button";

interface StationDetailsPanelProps {
  station: Station;
  distanceKm?: number;
  onClose?: () => void;
  onStartCharging?: () => void;
  startChargingLabel?: string;
  busy?: boolean;
  className?: string;
  onReserve?: () => void;
  reserving?: boolean;
  reservedPortNumber?: number | null;
}

// Mirrors simulation/station_sim.py's STATION_PROFILES mean_session_minutes
// per type - the two services communicate only over MQTT (no cross-import),
// so this is a deliberate, small, documented duplication rather than a
// shared dependency, same pattern as backend/app/services/fault_consumer.py's
// SIMULATION_STATION_COORDS.
const MEAN_SESSION_MINUTES: Record<string, number> = {
  public_dc_hub: 20, highway_corridor: 18, housing_society_ac: 300,
};

function estimateWaitMinutes(station: Station): number | null {
  if (station.queue_length <= 0) return null;
  const meanSession = MEAN_SESSION_MINUTES[station.station_type] ?? 25;
  const chargerCount = Math.max(1, station.chargers.length);
  return Math.round((station.queue_length * meanSession) / chargerCount);
}

function ChargerTypeSummary({ type, chargers }: { type: "AC" | "DC"; chargers: Station["chargers"] }) {
  const ofType = chargers.filter((c) => c.charger_type === type);
  if (ofType.length === 0) return null;
  const available = ofType.filter((c) => c.status === "available").length;
  const Icon = type === "DC" ? LightningIcon : PlugsIcon;

  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.03] p-3">
      <p className="text-xs font-semibold flex items-center gap-1.5 mb-1.5">
        <Icon size={14} weight={type === "DC" ? "fill" : "regular"} className={type === "DC" ? "text-cyan-300" : "text-emerald-300"} />
        {type === "DC" ? "DC Fast" : "AC"}
      </p>
      <p className={`text-xs ${available > 0 ? "text-emerald-400" : "text-red-400"}`}>
        {available} of {ofType.length} available
      </p>
      <p className="text-[11px] text-slate-500 mt-1">~₹{RATE_PER_KWH[type]}/kWh</p>
      <div className="flex flex-wrap gap-1 mt-2">
        {ofType.map((c) => (
          <span key={c.id}
                className={`text-[10px] font-mono px-1.5 py-0.5 rounded ${
                  c.status === "available" ? "bg-emerald-500/15 text-emerald-300" : "bg-white/10 text-slate-500"
                }`}>
            {c.port_number !== null ? `#${c.port_number}` : "?"}
          </span>
        ))}
      </div>
    </div>
  );
}

export function StationDetailsPanel({
  station, distanceKm, onClose, onStartCharging, startChargingLabel = "Start charging here", busy, className,
  onReserve, reserving, reservedPortNumber,
}: StationDetailsPanelProps) {
  const waitMinutes = estimateWaitMinutes(station);
  return (
    <GlassCard className={className}>
      <div className="flex items-start justify-between gap-3 mb-3">
        <div>
          <p className="font-medium flex items-center gap-1.5">
            <MapPinIcon size={16} className="text-emerald-400" /> {formatStationType(station.station_type)}
          </p>
          {station.city && <p className="text-xs text-slate-500 mt-0.5">{station.city}</p>}
        </div>
        {onClose && (
          <button onClick={onClose} className="cursor-pointer text-slate-400 hover:text-slate-200 shrink-0">
            <XIcon size={18} />
          </button>
        )}
      </div>

      <div className="flex flex-wrap gap-1.5 mb-3">
        <span className={`text-[11px] px-2 py-0.5 rounded-full inline-flex items-center gap-1 ${safetyBadgeClasses(station.safety_score)}`}>
          <ShieldCheckIcon size={11} weight="fill" /> Safety {(station.safety_score * 100).toFixed(0)}%
        </span>
        {station.has_solar && (
          <span className="text-[11px] px-2 py-0.5 rounded-full inline-flex items-center gap-1 bg-amber-100 text-amber-900 dark:bg-amber-900 dark:text-amber-100">
            <SunIcon size={11} weight="fill" /> Solar-powered
          </span>
        )}
        {distanceKm !== undefined && (
          <span className="text-[11px] px-2 py-0.5 rounded-full inline-flex items-center gap-1 bg-white/10 text-slate-300">
            <RulerIcon size={11} /> {distanceKm.toFixed(1)} km away
          </span>
        )}
        {waitMinutes !== null && (
          <span className="text-[11px] px-2 py-0.5 rounded-full inline-flex items-center gap-1 bg-amber-500/15 text-amber-300">
            <HourglassIcon size={11} weight="fill" /> ~{waitMinutes} min wait ({station.queue_length} waiting)
          </span>
        )}
      </div>

      <div className="grid grid-cols-2 gap-2 mb-3">
        <ChargerTypeSummary type="DC" chargers={station.chargers} />
        <ChargerTypeSummary type="AC" chargers={station.chargers} />
      </div>

      {station.swap_slots.length > 0 && (
        <p className="text-xs text-slate-400 flex items-center gap-1.5 mb-3">
          <ArrowsLeftRightIcon size={13} /> {station.swap_slots.reduce((sum, s) => sum + s.batteries_available, 0)} swap batteries available
        </p>
      )}

      {reservedPortNumber != null ? (
        <p className="text-xs text-cyan-300 flex items-center gap-1.5 mb-2">
          <BookmarkSimpleIcon size={14} weight="fill" /> Port {reservedPortNumber} held for you (10 min)
        </p>
      ) : onReserve && (
        <Button fullWidth variant="secondary" onClick={onReserve} disabled={reserving} className="mb-2">
          <BookmarkSimpleIcon size={16} /> {reserving ? "Reserving..." : "Reserve a port (10 min hold)"}
        </Button>
      )}

      {onStartCharging && (
        <Button fullWidth onClick={onStartCharging} disabled={busy}>
          <NavigationArrowIcon size={16} weight="fill" /> {busy ? "Starting..." : startChargingLabel}
        </Button>
      )}
    </GlassCard>
  );
}
