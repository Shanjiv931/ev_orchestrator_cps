import type { ReactNode } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "./auth/AuthContext";
import { Layout } from "./components/Layout";
import { LoginPage } from "./pages/LoginPage";
import { RegisterPage } from "./pages/RegisterPage";
import { MapPage } from "./pages/MapPage";
import { StationsPage } from "./pages/StationsPage";
import { VehiclesPage } from "./pages/VehiclesPage";
import { SessionsPage } from "./pages/SessionsPage";
import { AdminPage } from "./pages/AdminPage";

function ProtectedRoute({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="p-8 text-center">Loading...</div>;
  if (!user) return <Navigate to="/login" replace />;
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
      <Route element={<ProtectedRoute><Layout /></ProtectedRoute>}>
        <Route index element={<DefaultRoute />} />
        <Route path="map" element={<MapPage />} />
        <Route path="stations" element={<StationsPage />} />
        <Route path="vehicles" element={<VehiclesPage />} />
        <Route path="sessions" element={<SessionsPage />} />
        <Route path="admin" element={<AdminPage />} />
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
