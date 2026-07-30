import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { EnvelopeSimpleIcon } from "@phosphor-icons/react";
import { useAuth } from "../auth/AuthContext";
import { ApiError } from "../api/client";
import { GlassCard } from "../components/ui/GlassCard";
import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Input";

interface LocationState {
  pendingRegistrationId?: string;
  email?: string;
}

export function VerifyOtpPage() {
  const { verifyOtp, resendOtp } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const { pendingRegistrationId, email } = (location.state ?? {}) as LocationState;

  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [resending, setResending] = useState(false);

  useEffect(() => {
    // No pending registration to verify (direct link, refresh, or the OTP
    // page reached some other way) - nothing to do here but register again.
    if (!pendingRegistrationId) navigate("/register", { replace: true });
  }, [pendingRegistrationId, navigate]);

  if (!pendingRegistrationId) return null;

  async function handleSubmit() {
    setError(null);
    setNotice(null);
    setSubmitting(true);
    try {
      await verifyOtp(pendingRegistrationId!, code);
      navigate("/onboarding/location");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Verification failed");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleResend() {
    setError(null);
    setNotice(null);
    setResending(true);
    try {
      await resendOtp(pendingRegistrationId!);
      setNotice("If that address is valid, a new code is on its way.");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't resend the code");
    } finally {
      setResending(false);
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
          <EnvelopeSimpleIcon size={36} weight="duotone" className="mx-auto text-emerald-400 mb-2" />
          <h1 className="font-display text-xl font-bold">Confirm your email</h1>
          <p className="text-sm text-slate-500 mt-1">
            If <span className="text-slate-300">{email}</span> is valid, you'll receive a 6-digit code shortly.
          </p>
        </div>

        <GlassCard className="p-6">
          <div className="flex flex-col gap-3">
            <Input
              inputMode="numeric"
              maxLength={6}
              placeholder="000000"
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
              className="text-center text-2xl tracking-[0.5em] font-display"
            />
            {error && <p className="text-red-400 text-sm">{error}</p>}
            {notice && <p className="text-emerald-400 text-sm">{notice}</p>}
            <Button fullWidth onClick={handleSubmit} disabled={submitting || code.length !== 6}>
              {submitting ? "Verifying..." : "Confirm"}
            </Button>
            <Button variant="ghost" fullWidth onClick={handleResend} disabled={resending}>
              {resending ? "Sending..." : "Resend code"}
            </Button>
          </div>
        </GlassCard>

        <button
          onClick={() => navigate("/register", { replace: true })}
          className="mt-5 w-full text-center text-sm text-slate-500 hover:text-slate-300 underline underline-offset-4 cursor-pointer"
        >
          Use a different account
        </button>
      </motion.div>
    </div>
  );
}
