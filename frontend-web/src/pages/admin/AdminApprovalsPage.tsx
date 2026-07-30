import { useEffect, useState } from "react";
import { ShieldCheckIcon } from "@phosphor-icons/react";
import { api } from "../../api/client";
import type { AdminRequest } from "../../api/types";
import { GlassCard } from "../../components/ui/GlassCard";
import { Button } from "../../components/ui/Button";

export function AdminApprovalsPage() {
  const [requests, setRequests] = useState<AdminRequest[]>([]);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    try {
      const data = await api.get<AdminRequest[]>("/admin/requests?status_filter=pending");
      setRequests(data);
    } catch {
      setError("You need admin access to view this page.");
    }
  }

  useEffect(() => { refresh(); }, []);

  async function approve(id: string) {
    await api.post(`/admin/requests/${id}/approve`);
    refresh();
  }

  async function reject(id: string) {
    await api.post(`/admin/requests/${id}/reject`);
    refresh();
  }

  return (
    <div>
      <div className="flex items-center gap-2 mb-6">
        <ShieldCheckIcon size={24} weight="duotone" className="text-emerald-400" />
        <h1 className="font-display text-2xl font-bold">Admin approval requests</h1>
      </div>

      {error && <p className="text-red-400 text-sm">{error}</p>}

      {requests.length === 0 && !error && (
        <p className="text-sm text-slate-500">No pending requests right now.</p>
      )}

      <div className="flex flex-col gap-3">
        {requests.map((r) => (
          <GlassCard key={r.id} className="flex items-center justify-between gap-4 flex-wrap">
            <div className="text-sm">
              <p className="font-mono text-xs text-slate-500">user {r.user_id.slice(0, 8)}</p>
              <p className="text-slate-400">Requested {new Date(r.requested_at).toLocaleString()}</p>
            </div>
            <div className="flex gap-2">
              <Button variant="ghost" onClick={() => reject(r.id)}>Reject</Button>
              <Button onClick={() => approve(r.id)}>Approve</Button>
            </div>
          </GlassCard>
        ))}
      </div>
    </div>
  );
}
