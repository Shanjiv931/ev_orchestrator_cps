import { useEffect, useState } from "react";
import { UsersIcon } from "@phosphor-icons/react";
import { api } from "../../api/client";
import type { User } from "../../api/types";
import { GlassCard } from "../../components/ui/GlassCard";

const PERSONA_COLORS: Record<string, string> = {
  city_admin: "bg-amber-500/15 text-amber-300 border-amber-400/30",
  fleet_operator: "bg-cyan-500/15 text-cyan-300 border-cyan-400/30",
  housing_society_resident: "bg-purple-500/15 text-purple-300 border-purple-400/30",
  individual_driver: "bg-emerald-500/15 text-emerald-300 border-emerald-400/30",
};

export function AdminUsersPage() {
  const [users, setUsers] = useState<User[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.get<User[]>("/admin/users").then(setUsers).catch(() => setError("You need admin access to view this page."));
  }, []);

  return (
    <div>
      <div className="flex items-center gap-2 mb-6">
        <UsersIcon size={24} weight="duotone" className="text-emerald-400" />
        <h1 className="font-display text-2xl font-bold">All registered users</h1>
      </div>

      {error && <p className="text-red-400 text-sm">{error}</p>}

      {users && (
        <GlassCard className="p-0 overflow-hidden overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-left text-slate-400 border-b border-white/10">
              <tr>
                <th className="px-4 py-3 font-medium">Name</th>
                <th className="px-4 py-3 font-medium">Email</th>
                <th className="px-4 py-3 font-medium">Persona</th>
                <th className="px-4 py-3 font-medium">Auth</th>
                <th className="px-4 py-3 font-medium">Location</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id} className="border-b border-white/5 hover:bg-white/[0.03] transition-colors">
                  <td className="px-4 py-3">{u.name}</td>
                  <td className="px-4 py-3 text-slate-400">{u.email}</td>
                  <td className="px-4 py-3">
                    <span className={`text-xs px-2 py-0.5 rounded-full border ${PERSONA_COLORS[u.persona] ?? ""}`}>
                      {u.persona}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-slate-400">{u.auth_provider}</td>
                  <td className="px-4 py-3 text-slate-400">{u.location_city ?? "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </GlassCard>
      )}
    </div>
  );
}
