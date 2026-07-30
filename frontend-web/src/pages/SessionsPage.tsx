import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { ListChecksIcon, LeafIcon, LightningIcon, QrCodeIcon } from "@phosphor-icons/react";
import { api } from "../api/client";
import type { ChargingSession, Vehicle } from "../api/types";
import { GlassCard } from "../components/ui/GlassCard";
import { Button } from "../components/ui/Button";
import { Select } from "../components/ui/Input";

interface PaymentInfo {
  reference: string;
  amount_rupees: number;
  qr_payload: string;
  status: string;
  note: string;
}

interface CarbonSummary {
  total_co2_avoided_kg: number;
  session_count: number;
}

export function SessionsPage() {
  const { t } = useTranslation();
  const [sessions, setSessions] = useState<ChargingSession[]>([]);
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [selectedVehicleId, setSelectedVehicleId] = useState("");
  const [isEmergency, setIsEmergency] = useState(false);
  const [payment, setPayment] = useState<PaymentInfo | null>(null);
  const [carbonSummary, setCarbonSummary] = useState<CarbonSummary | null>(null);

  async function refresh() {
    const [s, v, c] = await Promise.all([
      api.get<ChargingSession[]>("/sessions"),
      api.get<Vehicle[]>("/vehicles"),
      api.get<CarbonSummary>("/carbon-ledger/me/summary"),
    ]);
    setSessions(s);
    setVehicles(v);
    setCarbonSummary(c);
    if (v.length > 0 && !selectedVehicleId) setSelectedVehicleId(v[0].id);
  }

  useEffect(() => { refresh(); }, []);

  async function startSession() {
    if (!selectedVehicleId) return;
    await api.post("/sessions", { vehicle_id: selectedVehicleId, is_emergency_priority: isEmergency });
    refresh();
  }

  async function completeSession(sessionId: string) {
    await api.patch(`/sessions/${sessionId}`, { energy_kwh: 15.0, cost: 225.0 });
    await api.post(`/sessions/${sessionId}/complete`);
    refresh();
  }

  async function initiatePayment(sessionId: string) {
    const p = await api.post<PaymentInfo>(`/payments/sessions/${sessionId}/initiate`);
    setPayment(p);
  }

  async function confirmPayment() {
    if (!payment) return;
    const updated = await api.post<{ reference: string; status: string }>(`/payments/${payment.reference}/confirm`);
    setPayment((prev) => (prev ? { ...prev, status: updated.status } : prev));
  }

  return (
    <div>
      <div className="flex items-center gap-2 mb-4">
        <ListChecksIcon size={24} weight="duotone" className="text-emerald-400" />
        <h1 className="font-display text-2xl font-bold">{t("sessions.title")}</h1>
      </div>

      {carbonSummary && (
        <div className="mb-4 text-sm bg-emerald-500/10 border border-emerald-400/20 rounded-lg px-3 py-2 inline-flex items-center gap-2">
          <LeafIcon size={16} weight="fill" className="text-emerald-400" />
          {t("sessions.carbonSummary")}: <strong>{carbonSummary.total_co2_avoided_kg} kg CO2</strong>
        </div>
      )}

      {vehicles.length > 0 && (
        <GlassCard className="flex flex-wrap items-center gap-3 mb-6">
          <Select value={selectedVehicleId} onChange={(e) => setSelectedVehicleId(e.target.value)} className="w-auto">
            {vehicles.map((v) => (
              <option key={v.id} value={v.id} className="bg-slate-900">
                {v.brand ? `${v.brand} ${v.vehicle_model}` : `${v.vehicle_class} - ${v.connector_type}`}
              </option>
            ))}
          </Select>
          <label className="flex items-center gap-1.5 text-sm text-slate-300">
            <input type="checkbox" checked={isEmergency} onChange={(e) => setIsEmergency(e.target.checked)} />
            {t("sessions.emergency")}
          </label>
          <Button onClick={startSession}>{t("sessions.start")}</Button>
        </GlassCard>
      )}

      {payment && (
        <GlassCard glow="brand" className="mb-6 max-w-sm">
          <p className="text-xs uppercase tracking-wide text-amber-400 font-semibold mb-1 flex items-center gap-1">
            <QrCodeIcon size={14} /> {payment.note}
          </p>
          <p className="text-sm mb-2">₹{payment.amount_rupees.toFixed(2)} &middot; {payment.reference}</p>
          <p className="text-xs break-all text-slate-500 mb-3 font-mono bg-black/20 rounded p-2">{payment.qr_payload}</p>
          <p className="text-sm mb-2">Status: <strong>{payment.status}</strong></p>
          {payment.status === "pending" && <Button onClick={confirmPayment}>{t("sessions.pay")}</Button>}
        </GlassCard>
      )}

      <div className="space-y-3">
        {sessions.map((s) => (
          <GlassCard key={s.id} className="flex flex-wrap items-center justify-between gap-2">
            <div className="text-sm">
              <span className="font-mono text-xs text-slate-500">{s.id.slice(0, 8)}</span>
              {s.is_emergency_priority && (
                <span className="ml-2 text-xs bg-red-500/15 text-red-300 border border-red-400/30 px-2 py-0.5 rounded-full inline-flex items-center gap-1">
                  <LightningIcon size={10} weight="fill" /> {t("sessions.emergency")}
                </span>
              )}
              <p>{t("sessions.energy")}: {s.energy_kwh} &middot; {t("sessions.cost")}: ₹{s.cost}</p>
              <p className="text-slate-500">{s.end_time ? "Completed" : "In progress"}</p>
            </div>
            <div className="flex gap-2">
              {!s.end_time && <Button variant="ghost" onClick={() => completeSession(s.id)}>{t("sessions.complete")}</Button>}
              {s.end_time && <Button variant="ghost" onClick={() => initiatePayment(s.id)}>{t("sessions.pay")}</Button>}
            </div>
          </GlassCard>
        ))}
      </div>
    </div>
  );
}
