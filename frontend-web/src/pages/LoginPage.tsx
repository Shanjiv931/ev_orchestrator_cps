import { useState, type FormEvent } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAuth } from "../auth/AuthContext";

export function LoginPage() {
  const { t } = useTranslation();
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(email, password);
      navigate("/map");
    } catch {
      setError(t("auth.error"));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="max-w-sm mx-auto mt-16">
      <h1 className="text-2xl font-semibold mb-6">{t("auth.login")}</h1>
      <form onSubmit={handleSubmit} className="flex flex-col gap-3">
        <input type="email" required placeholder={t("auth.email")} value={email}
               onChange={(e) => setEmail(e.target.value)}
               className="border rounded-md px-3 py-2 dark:bg-slate-900 dark:border-slate-700" />
        <input type="password" required placeholder={t("auth.password")} value={password}
               onChange={(e) => setPassword(e.target.value)}
               className="border rounded-md px-3 py-2 dark:bg-slate-900 dark:border-slate-700" />
        {error && <p className="text-red-600 text-sm">{error}</p>}
        <button type="submit" disabled={submitting}
                className="bg-emerald-600 text-white rounded-md px-3 py-2 disabled:opacity-50">
          {t("auth.submit")}
        </button>
      </form>
      <p className="mt-4 text-sm">
        {t("auth.needAccount")} <Link to="/register" className="text-emerald-600 underline">{t("auth.register")}</Link>
      </p>
    </div>
  );
}
