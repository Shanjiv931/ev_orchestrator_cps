import { useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { motion } from "framer-motion";
import {
  MapTrifoldIcon, BatteryChargingIcon, CarIcon, ListChecksIcon,
  SquaresFourIcon, UsersIcon, ShieldCheckIcon, HeartbeatIcon, GlobeIcon, SignOutIcon,
} from "@phosphor-icons/react";
import { useAuth } from "../auth/AuthContext";
import { useOnlineStatus } from "../hooks/useOnlineStatus";
import { api } from "../api/client";

interface NavItem {
  to: string;
  label: string;
  icon: React.ReactNode;
}

const DRIVER_NAV: NavItem[] = [
  { to: "/map", label: "Map", icon: <MapTrifoldIcon size={22} weight="duotone" /> },
  { to: "/stations", label: "Stations", icon: <BatteryChargingIcon size={22} weight="duotone" /> },
  { to: "/vehicles", label: "Vehicles", icon: <CarIcon size={22} weight="duotone" /> },
  { to: "/sessions", label: "Sessions", icon: <ListChecksIcon size={22} weight="duotone" /> },
];

const ADMIN_NAV: NavItem[] = [
  { to: "/admin", label: "Dashboard", icon: <SquaresFourIcon size={22} weight="duotone" /> },
  { to: "/admin/station-health", label: "Stations", icon: <HeartbeatIcon size={22} weight="duotone" /> },
  { to: "/admin/approvals", label: "Approvals", icon: <ShieldCheckIcon size={22} weight="duotone" /> },
  { to: "/admin/users", label: "Users", icon: <UsersIcon size={22} weight="duotone" /> },
];

export function Layout() {
  const { i18n } = useTranslation();
  const { user, logout } = useAuth();
  const isOnline = useOnlineStatus();
  const location = useLocation();
  const [adminRequestState, setAdminRequestState] = useState<"idle" | "sent" | "error">("idle");

  const navItems = user?.persona === "city_admin" ? ADMIN_NAV : DRIVER_NAV;

  async function requestAdminAccess() {
    try {
      await api.post("/admin/requests");
      setAdminRequestState("sent");
    } catch {
      setAdminRequestState("error");
    }
  }

  return (
    <div className="min-h-screen flex flex-col pb-20">
      {!isOnline && (
        <div className="bg-amber-500/90 text-amber-950 text-center text-xs sm:text-sm py-1.5 px-2" role="status">
          You're offline - showing the last known station list.
        </div>
      )}
      <header className="sticky top-0 z-30 glass-panel border-x-0 border-t-0 px-4 py-3 flex items-center justify-between">
        <span className="font-display font-bold text-lg bg-gradient-to-br from-emerald-300 to-cyan-400 bg-clip-text text-transparent">
          MeridianGrid
        </span>
        <div className="flex items-center gap-2">
          {user && user.persona !== "city_admin" && (
            <button
              onClick={requestAdminAccess}
              disabled={adminRequestState === "sent"}
              className="hidden sm:inline text-xs px-2.5 py-1.5 rounded-lg border border-white/10 text-slate-400 hover:bg-white/5 cursor-pointer disabled:opacity-50"
            >
              {adminRequestState === "sent" ? "Request sent" : adminRequestState === "error" ? "Already requested" : "Request admin"}
            </button>
          )}
          <button
            onClick={() => i18n.changeLanguage(i18n.language.startsWith("hi") ? "en" : "hi")}
            className="flex items-center gap-1 text-xs px-2.5 py-1.5 rounded-lg border border-white/10 text-slate-300 hover:bg-white/5 cursor-pointer"
            aria-label="Toggle language"
          >
            <GlobeIcon size={14} /> {i18n.language.startsWith("hi") ? "EN" : "हिं"}
          </button>
          {user && (
            <button onClick={logout} aria-label="Log out"
                    className="flex items-center gap-1 text-xs px-2.5 py-1.5 rounded-lg border border-white/10 text-slate-300 hover:bg-white/5 cursor-pointer">
              <SignOutIcon size={14} />
            </button>
          )}
        </div>
      </header>

      <main className="flex-1 p-4 max-w-6xl w-full mx-auto">
        <Outlet />
      </main>

      <nav className="fixed bottom-0 inset-x-0 z-30 glass-panel border-x-0 border-b-0 flex justify-around px-2 py-2"
           style={{ paddingBottom: "max(0.5rem, env(safe-area-inset-bottom))" }}>
        {navItems.map((item) => {
          const isActive = location.pathname === item.to || (item.to !== "/admin" && location.pathname.startsWith(item.to));
          return (
            <NavLink key={item.to} to={item.to}
                     className="relative flex flex-col items-center gap-0.5 px-3 py-1.5 min-w-16 text-xs">
              {isActive && (
                <motion.div layoutId="nav-pill" className="absolute inset-0 rounded-xl bg-emerald-500/15"
                            transition={{ type: "spring", stiffness: 380, damping: 30 }} />
              )}
              <span className={`relative z-10 ${isActive ? "text-emerald-400" : "text-slate-500"}`}>{item.icon}</span>
              <span className={`relative z-10 ${isActive ? "text-emerald-300" : "text-slate-500"}`}>{item.label}</span>
            </NavLink>
          );
        })}
      </nav>
    </div>
  );
}
