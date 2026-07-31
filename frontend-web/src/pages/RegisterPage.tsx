import { useState, type FormEvent } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { motion } from "framer-motion";
import { useAuth } from "../auth/AuthContext";
import { ApiError } from "../api/client";
import type { Persona } from "../api/types";
import { GlassCard } from "../components/ui/GlassCard";
import { Button } from "../components/ui/Button";
import { Input, Select, FieldLabel } from "../components/ui/Input";
import { GoogleSignInButton } from "../components/GoogleSignInButton";

// city_admin is deliberately excluded - nobody can self-register as admin,
// see backend app/routers/admin.py's approval workflow.
const PERSONAS: Persona[] = ["individual_driver", "fleet_operator", "housing_society_resident"];

// Sixteen years ago-ish max, so the date picker doesn't default somewhere
// that instantly fails the backend's real "at least 18" check.
const MAX_DOB = new Date(Date.now() - 18 * 365.25 * 24 * 60 * 60 * 1000).toISOString().slice(0, 10);

export function RegisterPage() {
  const { t } = useTranslation();
  const { register } = useAuth();
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [persona, setPersona] = useState<Persona>("individual_driver");
  const [dateOfBirth, setDateOfBirth] = useState("");
  const [phoneNumber, setPhoneNumber] = useState("");
  const [licenseNumber, setLicenseNumber] = useState("");
  const [licenseExpiry, setLicenseExpiry] = useState("");
  const [profession, setProfession] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const pending = await register({
        name, email, password, persona,
        dateOfBirth, phoneNumber, licenseNumber, licenseExpiry, profession,
      });
      navigate("/verify-otp", { state: pending });
    } catch (err) {
      console.error("Registration failed:", err);
      setError(err instanceof ApiError ? err.message : "Couldn't reach the server - check your connection and try again");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-10">
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="w-full max-w-sm"
      >
        <div className="text-center mb-6">
          <h1 className="font-display text-2xl font-bold bg-gradient-to-br from-emerald-300 to-cyan-400 bg-clip-text text-transparent">
            MeridianGrid
          </h1>
          <p className="text-sm text-slate-500 mt-1">{t("auth.register")}</p>
        </div>

        <GlassCard className="p-6">
          <div className="flex flex-col gap-3 mb-5">
            <GoogleSignInButton onDone={() => navigate("/onboarding/location")} onError={setError} />
          </div>

          <div className="flex items-center gap-3 my-4">
            <div className="h-px flex-1 bg-white/10" />
            <span className="text-xs text-slate-500">or</span>
            <div className="h-px flex-1 bg-white/10" />
          </div>

          <form onSubmit={handleSubmit} className="flex flex-col gap-3">
            <Input required placeholder={t("auth.name")} value={name} onChange={(e) => setName(e.target.value)} />
            <Input type="email" required placeholder={t("auth.email")} value={email}
                   onChange={(e) => setEmail(e.target.value)} autoComplete="email" />
            <Input type="password" required placeholder={t("auth.password")} value={password}
                   onChange={(e) => setPassword(e.target.value)} autoComplete="new-password" />
            <Input type="tel" required placeholder="Phone number" value={phoneNumber}
                   onChange={(e) => setPhoneNumber(e.target.value)} autoComplete="tel" />
            <div>
              <FieldLabel>Date of birth</FieldLabel>
              <Input type="date" required max={MAX_DOB} value={dateOfBirth}
                     onChange={(e) => setDateOfBirth(e.target.value)} />
              <p className="text-xs text-slate-500 mt-1">Must be 18 or older.</p>
            </div>
            <Input required placeholder="Driving license number" value={licenseNumber}
                   onChange={(e) => setLicenseNumber(e.target.value)} />
            <div>
              <FieldLabel>License expiry date</FieldLabel>
              <Input type="date" required value={licenseExpiry}
                     onChange={(e) => setLicenseExpiry(e.target.value)} />
            </div>
            <Input required placeholder="Profession" value={profession}
                   onChange={(e) => setProfession(e.target.value)} />
            <div>
              <FieldLabel>{t("auth.persona")}</FieldLabel>
              <Select value={persona} onChange={(e) => setPersona(e.target.value as Persona)}>
                {PERSONAS.map((p) => (
                  <option key={p} value={p} className="bg-slate-900">{t(`persona.${p}`)}</option>
                ))}
              </Select>
              <p className="text-xs text-slate-500 mt-1">
                Need city admin access? Request it after signing up.
              </p>
            </div>
            {error && <p className="text-red-400 text-sm">{error}</p>}
            <Button type="submit" fullWidth disabled={submitting}>
              {t("auth.submit")}
            </Button>
          </form>
        </GlassCard>

        <p className="mt-5 text-center text-sm text-slate-500">
          {t("auth.haveAccount")}{" "}
          <Link to="/login" className="text-emerald-400 hover:text-emerald-300 underline underline-offset-4">
            {t("auth.login")}
          </Link>
        </p>
      </motion.div>
    </div>
  );
}
