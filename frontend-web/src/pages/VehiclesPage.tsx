import { useEffect, useMemo, useState } from "react";
import {
  CarIcon, PlusIcon, LinkIcon, BatteryChargingIcon, SparkleIcon,
  MagnifyingGlassIcon, TicketIcon, TrashIcon, XIcon, CheckCircleIcon, ClockIcon, XCircleIcon,
} from "@phosphor-icons/react";
import { api, ApiError } from "../api/client";
import type {
  BatteryHealth, MeridianGridLookupResponse, Vehicle, VehicleLiveTelemetry,
  VehiclePairingResponse, VehicleRequest,
} from "../api/types";
import { GlassCard } from "../components/ui/GlassCard";
import { Button } from "../components/ui/Button";
import { Input, Select, FieldLabel } from "../components/ui/Input";
import { CarScene } from "../components/3d/CarScene";
import { DELETE_REASON_OPTIONS } from "../lib/vehicleDeleteReasons";

const STATUS_STYLES: Record<VehicleRequest["status"], string> = {
  pending: "bg-amber-500/15 text-amber-300",
  approved: "bg-emerald-500/15 text-emerald-300",
  rejected: "bg-red-500/15 text-red-300",
};

function StatusBadge({ status }: { status: VehicleRequest["status"] }) {
  const Icon = status === "approved" ? CheckCircleIcon : status === "rejected" ? XCircleIcon : ClockIcon;
  return (
    <span className={`inline-flex items-center gap-1 text-[10px] font-medium px-2 py-0.5 rounded-full ${STATUS_STYLES[status]}`}>
      <Icon size={11} weight="fill" /> {status}
    </span>
  );
}

export function VehiclesPage() {
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [requests, setRequests] = useState<VehicleRequest[]>([]);
  const [health, setHealth] = useState<Record<string, BatteryHealth | null>>({});
  const [showAddForm, setShowAddForm] = useState(false);
  const [showRequests, setShowRequests] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [deletingVehicle, setDeletingVehicle] = useState<Vehicle | null>(null);

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
    api.get<VehicleRequest[]>("/vehicles/requests/mine").then(setRequests).catch(() => setRequests([]));
  }

  useEffect(() => { refresh(); }, []);

  const pendingCount = useMemo(() => requests.filter((r) => r.status === "pending").length, [requests]);

  return (
    <div className="pb-4">
      <div className="flex justify-between items-center mb-4 gap-2 flex-wrap">
        <div className="flex items-center gap-2">
          <CarIcon size={24} weight="duotone" className="text-emerald-400" />
          <h1 className="font-display text-2xl font-bold">My vehicles</h1>
        </div>
        <div className="flex gap-2">
          <Button variant="ghost" onClick={() => setShowRequests((s) => !s)}>
            <TicketIcon size={16} /> Requests{pendingCount > 0 && ` (${pendingCount})`}
          </Button>
          <Button onClick={() => setShowAddForm((s) => !s)}>
            <PlusIcon size={16} weight="bold" /> Add vehicle
          </Button>
        </div>
      </div>

      {showRequests && (
        <RequestsPanel requests={requests} onClose={() => setShowRequests(false)} />
      )}

      {showAddForm && (
        <AddVehicleForm onSubmitted={() => { setShowAddForm(false); refresh(); setShowRequests(true); }} />
      )}

      {deletingVehicle && (
        <DeleteVehicleForm
          vehicle={deletingVehicle}
          onClose={() => setDeletingVehicle(null)}
          onSubmitted={() => { setDeletingVehicle(null); refresh(); setShowRequests(true); }}
        />
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {vehicles.map((v) => (
          <VehicleCard key={v.id} vehicle={v} health={health[v.id] ?? null}
                       expanded={expandedId === v.id}
                       onToggle={() => setExpandedId(expandedId === v.id ? null : v.id)}
                       onPaired={refresh}
                       onRequestDelete={() => setDeletingVehicle(v)} />
        ))}
      </div>

      {vehicles.length === 0 && !showAddForm && (
        <p className="text-sm text-slate-500 mt-2">
          No vehicles yet. Every MeridianGrid-provisioned vehicle comes with an ID printed at delivery -
          enter it above to register.
        </p>
      )}
    </div>
  );
}

function RequestsPanel({ requests, onClose }: { requests: VehicleRequest[]; onClose: () => void }) {
  return (
    <GlassCard className="mb-6">
      <div className="flex items-center justify-between mb-3">
        <h2 className="font-medium text-sm">Your requests</h2>
        <button onClick={onClose} className="cursor-pointer text-slate-400 hover:text-slate-200"><XIcon size={16} /></button>
      </div>
      {requests.length === 0 ? (
        <p className="text-xs text-slate-500">No add or delete requests yet.</p>
      ) : (
        <ul className="divide-y divide-white/5">
          {requests.map((r) => (
            <li key={r.id} className="py-2.5 flex items-center justify-between gap-3 flex-wrap">
              <div>
                <p className="text-xs font-mono text-slate-300">{r.ticket_code}</p>
                <p className="text-[11px] text-slate-500">
                  {r.request_type === "add" ? `Add · ${r.meridiangrid_id}` : `Delete · ${r.reason_code?.replace(/_/g, " ")}`}
                  {" "}&middot; {new Date(r.created_at).toLocaleDateString()}
                </p>
                {r.admin_notes && <p className="text-[11px] text-slate-400 mt-0.5">Admin note: {r.admin_notes}</p>}
              </div>
              <StatusBadge status={r.status} />
            </li>
          ))}
        </ul>
      )}
    </GlassCard>
  );
}

function AddVehicleForm({ onSubmitted }: { onSubmitted: () => void }) {
  const [meridiangridId, setMeridiangridId] = useState("");
  const [lookup, setLookup] = useState<MeridianGridLookupResponse | null>(null);
  const [lookupError, setLookupError] = useState<string | null>(null);
  const [numberPlate, setNumberPlate] = useState("");
  const [busy, setBusy] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [ticket, setTicket] = useState<string | null>(null);

  async function runLookup() {
    setLookup(null);
    setLookupError(null);
    if (!meridiangridId.trim()) return;
    setBusy(true);
    try {
      const result = await api.get<MeridianGridLookupResponse>(`/vehicles/lookup/${encodeURIComponent(meridiangridId.trim())}`);
      setLookup(result);
    } catch (err) {
      setLookupError(err instanceof ApiError ? err.message : "Could not look up that ID.");
    } finally {
      setBusy(false);
    }
  }

  async function submit() {
    if (!lookup) return;
    setBusy(true);
    setSubmitError(null);
    try {
      const req = await api.post<VehicleRequest>("/vehicles/requests/add", {
        meridiangrid_id: lookup.meridiangrid_id, number_plate: numberPlate,
      });
      setTicket(req.ticket_code);
    } catch (err) {
      setSubmitError(err instanceof ApiError ? err.message : "Could not submit the request.");
    } finally {
      setBusy(false);
    }
  }

  if (ticket) {
    return (
      <GlassCard className="mb-6 text-center py-6">
        <CheckCircleIcon size={28} weight="fill" className="text-emerald-400 mx-auto mb-2" />
        <p className="text-sm font-medium">Request submitted</p>
        <p className="text-xs text-slate-400 mt-1">
          Ticket <span className="font-mono text-slate-200">{ticket}</span> - a Vellore admin will review it shortly.
        </p>
        <Button variant="secondary" className="mt-4" onClick={onSubmitted}>Done</Button>
      </GlassCard>
    );
  }

  return (
    <GlassCard className="mb-6">
      <p className="text-xs text-slate-400 mb-3">
        Every MeridianGrid vehicle ships with a unique ID, auto-read from the manufacturer at delivery -
        no manual spec entry needed.
      </p>
      <FieldLabel>MeridianGrid ID</FieldLabel>
      <div className="flex gap-2 mb-3">
        <Input value={meridiangridId} onChange={(e) => setMeridiangridId(e.target.value.toUpperCase())}
               placeholder="MG-XXXX-XXXX" className="font-mono" />
        <Button variant="secondary" onClick={runLookup} disabled={busy || !meridiangridId.trim()}>
          <MagnifyingGlassIcon size={16} />
        </Button>
      </div>

      {lookupError && <p className="text-red-400 text-xs mb-3">{lookupError}</p>}

      {lookup && (
        <>
          <div className="text-xs text-slate-300 bg-white/5 rounded-lg p-3 grid grid-cols-2 gap-1.5 mb-3">
            <span className="col-span-2 font-medium">{lookup.brand} {lookup.vehicle_model}</span>
            <span>Class: {lookup.vehicle_class}</span>
            <span>Connector: {lookup.connector_type}</span>
            <span>Chemistry: {lookup.battery_chemistry}</span>
            <span>Capacity: {lookup.battery_capacity_kwh} kWh</span>
          </div>
          <FieldLabel>Number plate (Vellore - TN 23)</FieldLabel>
          <Input value={numberPlate} onChange={(e) => setNumberPlate(e.target.value.toUpperCase())}
                 placeholder="TN 23 AB 1234" className="font-mono mb-3" />
          {submitError && <p className="text-red-400 text-xs mb-3">{submitError}</p>}
          <Button fullWidth onClick={submit} disabled={busy || !numberPlate.trim()}>
            {busy ? "Submitting..." : "Submit for admin approval"}
          </Button>
        </>
      )}
    </GlassCard>
  );
}

function DeleteVehicleForm({ vehicle, onClose, onSubmitted }: {
  vehicle: Vehicle; onClose: () => void; onSubmitted: () => void;
}) {
  const [reasonCode, setReasonCode] = useState(DELETE_REASON_OPTIONS[0].code);
  const [detail, setDetail] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      await api.post("/vehicles/requests/delete", {
        vehicle_id: vehicle.id, reason_code: reasonCode, reason_detail: detail || undefined,
      });
      onSubmitted();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not submit the request.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <GlassCard className="mb-6 border-red-400/30">
      <div className="flex items-center justify-between mb-3">
        <h2 className="font-medium text-sm">
          Request removal - {vehicle.brand ? `${vehicle.brand} ${vehicle.vehicle_model}` : vehicle.vehicle_class}
        </h2>
        <button onClick={onClose} className="cursor-pointer text-slate-400 hover:text-slate-200"><XIcon size={16} /></button>
      </div>
      <FieldLabel>Reason</FieldLabel>
      <Select value={reasonCode} onChange={(e) => setReasonCode(e.target.value)} className="mb-3">
        {DELETE_REASON_OPTIONS.map((opt) => (
          <option key={opt.code} value={opt.code} className="bg-slate-900">{opt.label}</option>
        ))}
      </Select>
      {reasonCode === "other" && (
        <>
          <FieldLabel>Please explain</FieldLabel>
          <Input value={detail} onChange={(e) => setDetail(e.target.value)} placeholder="What happened?" className="mb-3" />
        </>
      )}
      <p className="text-xs text-slate-500 mb-3">
        A Vellore admin reviews every removal - your vehicle stays registered until it's approved.
      </p>
      {error && <p className="text-red-400 text-xs mb-3">{error}</p>}
      <Button variant="danger" fullWidth onClick={submit} disabled={busy || (reasonCode === "other" && !detail.trim())}>
        {busy ? "Submitting..." : "Submit removal request"}
      </Button>
    </GlassCard>
  );
}

function VehicleCard({ vehicle, health, expanded, onToggle, onPaired, onRequestDelete }: {
  vehicle: Vehicle; health: BatteryHealth | null; expanded: boolean; onToggle: () => void;
  onPaired: () => void; onRequestDelete: () => void;
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
          {vehicle.number_plate && <p className="text-xs font-mono text-slate-400 mt-0.5">{vehicle.number_plate}</p>}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <button onClick={onToggle} className="text-xs text-cyan-300 hover:text-cyan-200 cursor-pointer flex items-center gap-1">
            <SparkleIcon size={14} weight="fill" /> {expanded ? "Hide" : "View"} 3D
          </button>
          <button onClick={onRequestDelete} className="text-xs text-red-400 hover:text-red-300 cursor-pointer" aria-label="Request removal">
            <TrashIcon size={14} />
          </button>
        </div>
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
