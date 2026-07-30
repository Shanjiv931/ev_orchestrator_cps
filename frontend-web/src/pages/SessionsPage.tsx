import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../api/client";
import type { ChargingSession, Vehicle } from "../api/types";

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
      <h1 className="text-2xl font-semibold mb-4">{t("sessions.title")}</h1>

      {carbonSummary && (
        <div className="mb-4 text-sm bg-emerald-50 dark:bg-emerald-950 rounded-lg px-3 py-2 inline-block">
          {t("sessions.carbonSummary")}: <strong>{carbonSummary.total_co2_avoided_kg} kg CO2</strong>
        </div>
      )}

      {vehicles.length > 0 && (
        <div className="flex flex-wrap items-center gap-3 mb-6 bg-slate-100 dark:bg-slate-900 p-3 rounded-lg">
          <select value={selectedVehicleId} onChange={(e) => setSelectedVehicleId(e.target.value)}
                  className="border rounded-md px-2 py-1 dark:bg-slate-800 dark:border-slate-700">
            {vehicles.map((v) => <option key={v.id} value={v.id}>{v.vehicle_class} - {v.connector_type}</option>)}
          </select>
          <label className="flex items-center gap-1 text-sm">
            <input type="checkbox" checked={isEmergency} onChange={(e) => setIsEmergency(e.target.checked)} />
            {t("sessions.emergency")}
          </label>
          <button onClick={startSession} className="bg-emerald-600 text-white rounded-md px-3 py-1.5 text-sm">
            {t("sessions.start")}
          </button>
        </div>
      )}

      {payment && (
        <div className="border-2 border-emerald-500 rounded-lg p-4 mb-6 max-w-sm">
          <p className="text-xs uppercase tracking-wide text-amber-600 font-semibold mb-1">{t("sessions.payNote")}</p>
          <p className="text-sm mb-2">₹{payment.amount_rupees.toFixed(2)} · {payment.reference}</p>
          <p className="text-xs break-all text-slate-500 mb-2 font-mono">{payment.qr_payload}</p>
          <p className="text-sm mb-2">Status: <strong>{payment.status}</strong></p>
          {payment.status === "pending" && (
            <button onClick={confirmPayment} className="bg-emerald-600 text-white rounded-md px-3 py-1.5 text-sm">
              {t("sessions.pay")}
            </button>
          )}
        </div>
      )}

      <div className="space-y-3">
        {sessions.map((s) => (
          <div key={s.id} className="border rounded-lg p-3 flex flex-wrap items-center justify-between gap-2 dark:border-slate-800">
            <div className="text-sm">
              <span className="font-mono text-xs text-slate-500">{s.id.slice(0, 8)}</span>
              {s.is_emergency_priority && <span className="ml-2 text-xs bg-red-100 text-red-700 px-2 py-0.5 rounded-full">🚨 {t("sessions.emergency")}</span>}
              <p>{t("sessions.energy")}: {s.energy_kwh} · {t("sessions.cost")}: ₹{s.cost}</p>
              <p className="text-slate-500">{s.end_time ? "Completed" : "In progress"}</p>
            </div>
            <div className="flex gap-2">
              {!s.end_time && (
                <button onClick={() => completeSession(s.id)} className="text-sm border rounded-md px-3 py-1.5 dark:border-slate-700">
                  {t("sessions.complete")}
                </button>
              )}
              {s.end_time && (
                <button onClick={() => initiatePayment(s.id)} className="text-sm border rounded-md px-3 py-1.5 dark:border-slate-700">
                  {t("sessions.pay")}
                </button>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
