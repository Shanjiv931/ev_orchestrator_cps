import { useState, type FormEvent } from "react";
import { useNavigate, Link } from "react-router-dom";
import { motion } from "framer-motion";
import { useAuth } from "../auth/AuthContext";
import { ApiError } from "../api/client";
import { GlassCard } from "../components/ui/GlassCard";
import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Input";
import { GoogleSignInButton } from "../components/GoogleSignInButton";
import { IntroSplash } from "../components/IntroSplash";

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [showIntro, setShowIntro] = useState(true);
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
      navigate("/");
    } catch (err) {
      console.error("Login failed:", err);
      // ApiError carries the backend's own message (e.g. "invalid email or
      // password") - safe to show directly. Anything else (network/CORS
      // failure before a response even comes back) gets a distinct message
      // instead of the same generic string, so a connectivity problem
      // doesn't look identical to a wrong password.
      setError(err instanceof ApiError ? err.message : "Couldn't reach the server - check your connection and try again");
    } finally {
      setSubmitting(false);
    }
  }

  if (showIntro) {
    return <IntroSplash onDone={() => setShowIntro(false)} />;
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
          <p className="text-sm text-slate-500 mt-1">Log in</p>
        </div>

        <GlassCard className="p-6">
          <div className="flex flex-col gap-3 mb-5">
            <GoogleSignInButton onDone={() => navigate("/")} onError={setError} />
          </div>

          <div className="flex items-center gap-3 my-4">
            <div className="h-px flex-1 bg-white/10" />
            <span className="text-xs text-slate-500">or</span>
            <div className="h-px flex-1 bg-white/10" />
          </div>

          <form onSubmit={handleSubmit} className="flex flex-col gap-3">
            <Input type="email" required placeholder="Email" value={email}
                   onChange={(e) => setEmail(e.target.value)} autoComplete="email" />
            <Input type="password" required placeholder="Password" value={password}
                   onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" />
            {error && <p className="text-red-400 text-sm">{error}</p>}
            <Button type="submit" fullWidth disabled={submitting}>
              Continue
            </Button>
          </form>
        </GlassCard>

        <p className="mt-5 text-center text-sm text-slate-500">
          Need an account?{" "}
          <Link to="/register" className="text-emerald-400 hover:text-emerald-300 underline underline-offset-4">
            Create account
          </Link>
        </p>
      </motion.div>
    </div>
  );
}
