import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api, setToken } from "../api/client";
import type { Persona, User } from "../api/types";

interface PendingRegistration {
  pendingRegistrationId: string;
  email: string;
}

// Nine positional params would be unreadable at the call site - a single
// object mirrors the backend's UserCreate schema field-for-field.
export interface RegisterInput {
  name: string;
  email: string;
  password: string;
  persona: Persona;
  dateOfBirth: string;
  phoneNumber: string;
  licenseNumber: string;
  licenseExpiry: string;
  profession: string;
}

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (input: RegisterInput) => Promise<PendingRegistration>;
  loginWithGoogle: (idToken: string) => Promise<void>;
  verifyOtp: (pendingRegistrationId: string, otpCode: string) => Promise<void>;
  resendOtp: (pendingRegistrationId: string) => Promise<void>;
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

  const register = useCallback(async (input: RegisterInput) => {
    // No token yet - registration isn't persisted (no User row exists) until
    // the OTP is verified, see backend/app/routers/auth.py.
    const response = await api.post<{ pending_registration_id: string; email: string }>("/auth/register", {
      name: input.name,
      email: input.email,
      password: input.password,
      persona: input.persona,
      dpdp_consent_flag: true,
      date_of_birth: input.dateOfBirth,
      phone_number: input.phoneNumber,
      license_number: input.licenseNumber,
      license_expiry: input.licenseExpiry,
      profession: input.profession,
    });
    return { pendingRegistrationId: response.pending_registration_id, email: response.email };
  }, []);

  const loginWithGoogle = useCallback(async (idToken: string) => {
    const { access_token } = await api.post<{ access_token: string }>("/oauth/google", { id_token: idToken });
    setToken(access_token);
    await loadCurrentUser();
  }, [loadCurrentUser]);

  const verifyOtp = useCallback(async (pendingRegistrationId: string, otpCode: string) => {
    // This is the point the account actually gets created server-side - see
    // backend/app/routers/auth.py's verify_otp. Only now does a real token exist.
    const { access_token } = await api.post<{ access_token: string }>("/auth/verify-otp", {
      pending_registration_id: pendingRegistrationId, otp_code: otpCode,
    });
    setToken(access_token);
    await loadCurrentUser();
  }, [loadCurrentUser]);

  const resendOtp = useCallback(async (pendingRegistrationId: string) => {
    await api.post("/auth/resend-otp", { pending_registration_id: pendingRegistrationId });
  }, []);

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
      user, loading, login, register, loginWithGoogle, verifyOtp, resendOtp, updateLocation, logout,
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
