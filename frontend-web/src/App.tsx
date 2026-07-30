import type { ReactNode } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "./auth/AuthContext";
import { Layout } from "./components/Layout";
import { LoginPage } from "./pages/LoginPage";
import { RegisterPage } from "./pages/RegisterPage";
import { OnboardingLocationPage } from "./pages/OnboardingLocationPage";
import { MapPage } from "./pages/MapPage";
import { StationsPage } from "./pages/StationsPage";
import { VehiclesPage } from "./pages/VehiclesPage";
import { SessionsPage } from "./pages/SessionsPage";
import { AdminPage } from "./pages/AdminPage";
import { AdminUsersPage } from "./pages/admin/AdminUsersPage";
import { AdminApprovalsPage } from "./pages/admin/AdminApprovalsPage";
import { StationHealthPage } from "./pages/admin/StationHealthPage";
import { Station3DPage } from "./pages/admin/Station3DPage";

function ProtectedRoute({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="min-h-screen flex items-center justify-center text-slate-500">Loading...</div>;
  if (!user) return <Navigate to="/login" replace />;
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
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
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
  );
}

export default function App() {
  return (
    <AuthProvider>
      <AppRoutes />
    </AuthProvider>
  );
}
