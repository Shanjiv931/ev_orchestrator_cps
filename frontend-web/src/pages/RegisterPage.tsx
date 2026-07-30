import { useState, type FormEvent } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAuth } from "../auth/AuthContext";
import type { Persona } from "../api/types";

const PERSONAS: Persona[] = ["individual_driver", "fleet_operator", "housing_society_resident", "city_admin"];

export function RegisterPage() {
  const { t } = useTranslation();
  const { register } = useAuth();
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [persona, setPersona] = useState<Persona>("individual_driver");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await register(name, email, password, persona);
      navigate("/map");
    } catch {
      setError(t("auth.error"));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="max-w-sm mx-auto mt-16">
      <h1 className="text-2xl font-semibold mb-6">{t("auth.register")}</h1>
      <form onSubmit={handleSubmit} className="flex flex-col gap-3">
        <input required placeholder={t("auth.name")} value={name} onChange={(e) => setName(e.target.value)}
               className="border rounded-md px-3 py-2 dark:bg-slate-900 dark:border-slate-700" />
        <input type="email" required placeholder={t("auth.email")} value={email}
               onChange={(e) => setEmail(e.target.value)}
               className="border rounded-md px-3 py-2 dark:bg-slate-900 dark:border-slate-700" />
        <input type="password" required placeholder={t("auth.password")} value={password}
               onChange={(e) => setPassword(e.target.value)}
               className="border rounded-md px-3 py-2 dark:bg-slate-900 dark:border-slate-700" />
        <label className="text-sm text-slate-600 dark:text-slate-400">{t("auth.persona")}</label>
        <select value={persona} onChange={(e) => setPersona(e.target.value as Persona)}
                className="border rounded-md px-3 py-2 dark:bg-slate-900 dark:border-slate-700">
          {PERSONAS.map((p) => (
            <option key={p} value={p}>{t(`persona.${p}`)}</option>
          ))}
        </select>
        {error && <p className="text-red-600 text-sm">{error}</p>}
        <button type="submit" disabled={submitting}
                className="bg-emerald-600 text-white rounded-md px-3 py-2 disabled:opacity-50">
          {t("auth.submit")}
        </button>
      </form>
      <p className="mt-4 text-sm">
        {t("auth.haveAccount")} <Link to="/login" className="text-emerald-600 underline">{t("auth.login")}</Link>
      </p>
    </div>
  );
}
