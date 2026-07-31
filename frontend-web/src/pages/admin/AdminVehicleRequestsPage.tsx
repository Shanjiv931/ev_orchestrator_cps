import { useEffect, useState } from "react";
import { CarIcon, PlusCircleIcon, TrashIcon } from "@phosphor-icons/react";
import { api } from "../../api/client";
import type { VehicleRequest } from "../../api/types";
import { GlassCard } from "../../components/ui/GlassCard";
import { Button } from "../../components/ui/Button";
import { Input } from "../../components/ui/Input";

export function AdminVehicleRequestsPage() {
  const [requests, setRequests] = useState<VehicleRequest[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notes, setNotes] = useState<Record<string, string>>({});

  async function refresh() {
    try {
      const data = await api.get<VehicleRequest[]>("/admin/vehicle-requests?status_filter=pending");
      setRequests(data);
    } catch {
      setError("You need admin access to view this page.");
    }
  }

  useEffect(() => { refresh(); }, []);

  async function approve(id: string) {
    await api.post(`/admin/vehicle-requests/${id}/approve`, { admin_notes: notes[id] || null });
    refresh();
  }

  async function reject(id: string) {
    await api.post(`/admin/vehicle-requests/${id}/reject`, { admin_notes: notes[id] || null });
    refresh();
  }

  return (
    <div>
      <div className="flex items-center gap-2 mb-6">
        <CarIcon size={24} weight="duotone" className="text-emerald-400" />
        <h1 className="font-display text-2xl font-bold">Vehicle requests</h1>
      </div>

      {error && <p className="text-red-400 text-sm">{error}</p>}

      {requests.length === 0 && !error && (
        <p className="text-sm text-slate-500">No pending vehicle requests right now.</p>
      )}

      <div className="flex flex-col gap-3">
        {requests.map((r) => (
          <GlassCard key={r.id} className="flex flex-col gap-3">
            <div className="flex items-start justify-between gap-4 flex-wrap">
              <div className="text-sm">
                <p className="flex items-center gap-1.5 font-medium">
                  {r.request_type === "add"
                    ? <PlusCircleIcon size={16} className="text-emerald-400" />
                    : <TrashIcon size={16} className="text-red-400" />}
                  {r.request_type === "add" ? "Add vehicle" : "Remove vehicle"}
                  <span className="font-mono text-xs text-slate-500 ml-1">{r.ticket_code}</span>
                </p>
                {r.request_type === "add" ? (
                  <p className="text-xs text-slate-400 mt-1">
                    ID {r.meridiangrid_id} &middot; Plate {r.number_plate}
                  </p>
                ) : (
                  <p className="text-xs text-slate-400 mt-1">
                    Reason: {r.reason_code?.replace(/_/g, " ")}
                    {r.reason_detail && ` - "${r.reason_detail}"`}
                  </p>
                )}
                <p className="text-xs text-slate-500 mt-1">
                  user {r.user_id.slice(0, 8)} &middot; requested {new Date(r.created_at).toLocaleString()}
                </p>
              </div>
            </div>
            <Input placeholder="Optional note for the user" value={notes[r.id] ?? ""}
                   onChange={(e) => setNotes((prev) => ({ ...prev, [r.id]: e.target.value }))}
                   className="text-xs" />
            <div className="flex gap-2 justify-end">
              <Button variant="ghost" onClick={() => reject(r.id)}>Reject</Button>
              <Button onClick={() => approve(r.id)}>Approve</Button>
            </div>
          </GlassCard>
        ))}
      </div>
    </div>
  );
}
