import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  ListChecksIcon, LeafIcon, LightningIcon, MapPinIcon, CheckCircleIcon,
  DeviceMobileIcon, CreditCardIcon, MoneyIcon,
} from "@phosphor-icons/react";
import { api } from "../api/client";
import type { ChargingSession, SessionPayment, Vehicle } from "../api/types";
import { GlassCard } from "../components/ui/GlassCard";
import { Button } from "../components/ui/Button";
import { Select } from "../components/ui/Input";

type PaymentMethod = "upi" | "card" | "cash";

const METHOD_META: Record<PaymentMethod, { label: string; icon: typeof DeviceMobileIcon }> = {
  upi: { label: "UPI", icon: DeviceMobileIcon },
  card: { label: "Card", icon: CreditCardIcon },
  cash: { label: "Cash", icon: MoneyIcon },
};

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
  const [openPayment, setOpenPayment] = useState<Record<string, SessionPayment | null>>({});
  const [payBusy, setPayBusy] = useState<string | null>(null);
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

  async function togglePaymentPrompt(sessionId: string) {
    if (openPayment[sessionId] !== undefined) {
      setOpenPayment((prev) => { const next = { ...prev }; delete next[sessionId]; return next; });
      return;
    }
    const info = await api.get<SessionPayment>(`/payments/sessions/${sessionId}`);
    setOpenPayment((prev) => ({ ...prev, [sessionId]: info }));
  }

  async function payAtStation(sessionId: string, method: PaymentMethod) {
    setPayBusy(sessionId);
    try {
      const info = await api.post<SessionPayment>(`/payments/sessions/${sessionId}/pay`, { method });
      setOpenPayment((prev) => ({ ...prev, [sessionId]: info }));
      setSessions((prev) => prev.map((s) => (s.id === sessionId
        ? { ...s, payment_status: info.payment_status, payment_method: info.payment_method, paid_at: info.paid_at }
        : s)));
    } finally {
      setPayBusy(null);
    }
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

      <div className="space-y-3">
        {sessions.map((s) => (
          <GlassCard key={s.id}>
            <div className="flex flex-wrap items-center justify-between gap-2">
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
              <div className="flex gap-2 items-center">
                {s.payment_status === "paid" ? (
                  <span className="text-xs text-emerald-300 flex items-center gap-1">
                    <CheckCircleIcon size={14} weight="fill" /> Paid via {s.payment_method}
                  </span>
                ) : (
                  <>
                    {!s.end_time && <Button variant="ghost" onClick={() => completeSession(s.id)}>{t("sessions.complete")}</Button>}
                    {s.end_time && <Button variant="ghost" onClick={() => togglePaymentPrompt(s.id)}>{t("sessions.pay")}</Button>}
                  </>
                )}
              </div>
            </div>

            {openPayment[s.id] && s.payment_status === "unpaid" && (
              <div className="mt-3 pt-3 border-t border-white/10">
                <p className="text-sm mb-2.5 flex items-center gap-1.5">
                  <MapPinIcon size={14} className="text-slate-400" />
                  Pay at <strong>{openPayment[s.id]!.station_name ?? "this station"}</strong>
                  {openPayment[s.id]!.station_id && (
                    <span className="font-mono text-xs text-slate-500">(ID: {openPayment[s.id]!.station_id!.slice(0, 8)})</span>
                  )}
                  ?
                </p>
                <div className="grid grid-cols-3 gap-2">
                  {(Object.keys(METHOD_META) as PaymentMethod[]).map((method) => {
                    const { label, icon: Icon } = METHOD_META[method];
                    return (
                      <button key={method} disabled={payBusy === s.id}
                              onClick={() => payAtStation(s.id, method)}
                              className="flex flex-col items-center gap-1 py-2.5 rounded-xl border border-white/10 bg-white/[0.03] hover:bg-white/[0.07] cursor-pointer transition-colors disabled:opacity-50 text-xs">
                        <Icon size={18} className="text-emerald-300" /> {label}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}
          </GlassCard>
        ))}
      </div>
    </div>
  );
}
