import { useState } from "react";
import { AdminUsersPage } from "./AdminUsersPage";
import { AdminDatabasePage } from "./AdminDatabasePage";

type Tab = "users" | "database";

export function AdminUsersDatabasePage() {
  const [tab, setTab] = useState<Tab>("users");

  return (
    <div>
      <div className="flex gap-2 mb-4">
        {(["users", "database"] as Tab[]).map((t) => (
          <button key={t} onClick={() => setTab(t)}
                  className={`text-sm px-3 py-1.5 rounded-lg cursor-pointer transition-colors ${
                    tab === t ? "bg-emerald-500/20 text-emerald-300" : "text-slate-400 hover:bg-white/5"
                  }`}>
            {t === "users" ? "Users" : "Database"}
          </button>
        ))}
      </div>
      {tab === "users" ? <AdminUsersPage /> : <AdminDatabasePage />}
    </div>
  );
}
