import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api, setToken } from "../api/client";
import type { Persona, User } from "../api/types";

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (name: string, email: string, password: string, persona: Persona) => Promise<void>;
  loginWithGoogle: (idToken: string) => Promise<void>;
  loginWithSimulatedApple: (simulatedAppleId: string, name: string) => Promise<void>;
  updateLocation: (locationState: string, locationCity: string, lat: number, lon: number) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const loadCurrentUser = useCallback(async () => {
    try {
      const me = await api.get<User>("/auth/me");
      setUser(me);
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadCurrentUser();
  }, [loadCurrentUser]);

  const login = useCallback(async (email: string, password: string) => {
    const { access_token } = await api.post<{ access_token: string }>("/auth/login", { email, password });
    setToken(access_token);
    await loadCurrentUser();
  }, [loadCurrentUser]);

  const register = useCallback(async (name: string, email: string, password: string, persona: Persona) => {
    const { access_token } = await api.post<{ access_token: string }>("/auth/register", {
      name, email, password, persona, dpdp_consent_flag: true,
    });
    setToken(access_token);
    await loadCurrentUser();
  }, [loadCurrentUser]);

  const loginWithGoogle = useCallback(async (idToken: string) => {
    const { access_token } = await api.post<{ access_token: string }>("/oauth/google", { id_token: idToken });
    setToken(access_token);
    await loadCurrentUser();
  }, [loadCurrentUser]);

  const loginWithSimulatedApple = useCallback(async (simulatedAppleId: string, name: string) => {
    const { access_token } = await api.post<{ access_token: string }>("/oauth/apple/simulated", {
      simulated_apple_id: simulatedAppleId, name,
    });
    setToken(access_token);
    await loadCurrentUser();
  }, [loadCurrentUser]);

  const updateLocation = useCallback(async (locationState: string, locationCity: string, lat: number, lon: number) => {
    const updated = await api.patch<User>("/auth/me/location", {
      location_state: locationState, location_city: locationCity, lat, lon,
    });
    setUser(updated);
  }, []);

  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{
      user, loading, login, register, loginWithGoogle, loginWithSimulatedApple, updateLocation, logout,
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}
