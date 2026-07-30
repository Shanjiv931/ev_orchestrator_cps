import { NavLink, Outlet } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAuth } from "../auth/AuthContext";
import { useOnlineStatus } from "../hooks/useOnlineStatus";

const navLinkClass = ({ isActive }: { isActive: boolean }) =>
  `px-3 py-2 rounded-md text-sm font-medium ${
    isActive ? "bg-emerald-600 text-white" : "text-slate-600 hover:bg-slate-200 dark:text-slate-300 dark:hover:bg-slate-800"
  }`;

export function Layout() {
  const { t, i18n } = useTranslation();
  const { user, logout } = useAuth();
  const isOnline = useOnlineStatus();

  return (
    <div className="min-h-screen flex flex-col">
      {!isOnline && (
        <div className="bg-amber-500 text-amber-950 text-center text-sm py-1 px-2" role="status">
          {t("offline.banner")}
        </div>
      )}
      <header className="border-b border-slate-200 dark:border-slate-800 px-4 py-3 flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-4 flex-wrap">
          <span className="font-semibold text-lg">{t("appName")}</span>
          <nav className="flex gap-1 flex-wrap">
            <NavLink to="/map" className={navLinkClass}>{t("nav.map")}</NavLink>
            <NavLink to="/stations" className={navLinkClass}>{t("nav.stations")}</NavLink>
            {user?.persona !== "city_admin" && (
              <>
                <NavLink to="/vehicles" className={navLinkClass}>{t("nav.vehicles")}</NavLink>
                <NavLink to="/sessions" className={navLinkClass}>{t("nav.sessions")}</NavLink>
              </>
            )}
            {user?.persona === "city_admin" && (
              <NavLink to="/admin" className={navLinkClass}>{t("nav.admin")}</NavLink>
            )}
          </nav>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => i18n.changeLanguage(i18n.language.startsWith("hi") ? "en" : "hi")}
            className="text-sm px-2 py-1 rounded border border-slate-300 dark:border-slate-700"
            aria-label="Toggle language"
          >
            {i18n.language.startsWith("hi") ? "EN" : "हिं"}
          </button>
          {user && (
            <button onClick={logout} className="text-sm px-2 py-1 rounded border border-slate-300 dark:border-slate-700">
              {t("nav.logout")}
            </button>
          )}
        </div>
      </header>
      <main className="flex-1 p-4">
        <Outlet />
      </main>
    </div>
  );
}
