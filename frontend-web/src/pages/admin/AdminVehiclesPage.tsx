import { useState } from "react";
import { AdminVehicleRequestsPage } from "./AdminVehicleRequestsPage";
import { AdminFleetPage } from "./AdminFleetPage";

type Tab = "requests" | "fleet";

export function AdminVehiclesPage() {
  const [tab, setTab] = useState<Tab>("requests");

  return (
    <div>
      <div className="flex gap-2 mb-4">
        {(["requests", "fleet"] as Tab[]).map((t) => (
          <button key={t} onClick={() => setTab(t)}
                  className={`text-sm px-3 py-1.5 rounded-lg cursor-pointer transition-colors ${
                    tab === t ? "bg-emerald-500/20 text-emerald-300" : "text-slate-400 hover:bg-white/5"
                  }`}>
            {t === "requests" ? "Pending requests" : "Vellore fleet"}
          </button>
        ))}
      </div>
      {tab === "requests" ? <AdminVehicleRequestsPage /> : <AdminFleetPage />}
    </div>
  );
}
