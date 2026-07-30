import { lazy, Suspense, type ReactNode } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "./auth/AuthContext";
import { Layout } from "./components/Layout";
import { FloatingPathsBackground } from "./components/ui/FloatingPathsBackground";

// Route-level code splitting - every page (plus the three.js scenes, Leaflet
// map, Recharts, and now Firebase Auth some of them pull in) was previously
// bundled into a single ~2.1MB chunk, which broke the production build:
// vite-plugin-pwa refuses to precache anything over its 2MB default and
// fails the build rather than silently skip it. Lazy-loading each page lets
// Vite split them into their own chunks, so no single one need approach
// that limit and the app only downloads what a given route actually needs.
const LoginPage = lazy(() => import("./pages/LoginPage").then((m) => ({ default: m.LoginPage })));
const RegisterPage = lazy(() => import("./pages/RegisterPage").then((m) => ({ default: m.RegisterPage })));
const VerifyOtpPage = lazy(() => import("./pages/VerifyOtpPage").then((m) => ({ default: m.VerifyOtpPage })));
const OnboardingLocationPage = lazy(() =>
  import("./pages/OnboardingLocationPage").then((m) => ({ default: m.OnboardingLocationPage })));
const MapPage = lazy(() => import("./pages/MapPage").then((m) => ({ default: m.MapPage })));
const StationsPage = lazy(() => import("./pages/StationsPage").then((m) => ({ default: m.StationsPage })));
const VehiclesPage = lazy(() => import("./pages/VehiclesPage").then((m) => ({ default: m.VehiclesPage })));
const SessionsPage = lazy(() => import("./pages/SessionsPage").then((m) => ({ default: m.SessionsPage })));
const AdminPage = lazy(() => import("./pages/AdminPage").then((m) => ({ default: m.AdminPage })));
const AdminUsersPage = lazy(() =>
  import("./pages/admin/AdminUsersPage").then((m) => ({ default: m.AdminUsersPage })));
const AdminApprovalsPage = lazy(() =>
  import("./pages/admin/AdminApprovalsPage").then((m) => ({ default: m.AdminApprovalsPage })));
const StationHealthPage = lazy(() =>
  import("./pages/admin/StationHealthPage").then((m) => ({ default: m.StationHealthPage })));
const Station3DPage = lazy(() =>
  import("./pages/admin/Station3DPage").then((m) => ({ default: m.Station3DPage })));

function RouteFallback() {
  return <div className="min-h-screen flex items-center justify-center text-slate-500">Loading...</div>;
}

function ProtectedRoute({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="min-h-screen flex items-center justify-center text-slate-500">Loading...</div>;
  if (!user) return <Navigate to="/login" replace />;
  // No dangling "authenticated but unverified" state is reachable anymore -
  // a token is only ever issued once verify-otp creates the User row (or,
  // for Google/Firebase sign-in, at account creation, since Google already
  // confirmed the email) - see backend/app/routers/auth.py.
  if (user.lat === null) return <Navigate to="/onboarding/location" replace />;
  return <>{children}</>;
}

function DefaultRoute() {
  const { user } = useAuth();
  // Each persona lands on a different default view, per Section 4.1 -
  // not just a different theme on the same screen.
  if (user?.persona === "city_admin") return <Navigate to="/admin" replace />;
  if (user?.persona === "fleet_operator") return <Navigate to="/vehicles" replace />;
  return <Navigate to="/map" replace />;
}

function AppRoutes() {
  return (
    <Suspense fallback={<RouteFallback />}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/verify-otp" element={<VerifyOtpPage />} />
        <Route path="/onboarding/location" element={<OnboardingLocationPage />} />
        <Route element={<ProtectedRoute><Layout /></ProtectedRoute>}>
          <Route index element={<DefaultRoute />} />
          <Route path="map" element={<MapPage />} />
          <Route path="stations" element={<StationsPage />} />
          <Route path="vehicles" element={<VehiclesPage />} />
          <Route path="sessions" element={<SessionsPage />} />
          <Route path="admin" element={<AdminPage />} />
          <Route path="admin/users" element={<AdminUsersPage />} />
          <Route path="admin/approvals" element={<AdminApprovalsPage />} />
          <Route path="admin/station-health" element={<StationHealthPage />} />
          <Route path="admin/stations/:stationId/3d" element={<Station3DPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  );
}

export default function App() {
  return (
    <AuthProvider>
      {/* fixed, behind everything (z-0, no pointer events) - the intro
          splash renders its own opaque fixed z-50 overlay from inside
          LoginPage/RegisterPage, so it naturally covers this rather than
          needing route-based exclusion logic.
          The outer div owns the fixed/inset-0 positioning: the component's
          own root already hardcodes "relative", so passing "fixed inset-0"
          as its className collided on the same element - position is a
          single CSS property, and "relative" was winning the cascade,
          collapsing the whole thing to height:0 (no explicit height, and
          absolutely-positioned children don't contribute to parent height)
          - invisible, but still "mounted" as far as the DOM was concerned. */}
      <div className="fixed inset-0 z-0 pointer-events-none">
        <FloatingPathsBackground position={-1} className="h-full" />
      </div>
      <div className="relative z-10">
        <AppRoutes />
      </div>
    </AuthProvider>
  );
}
