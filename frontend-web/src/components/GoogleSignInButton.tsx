import { useState } from "react";
import { signInWithPopup } from "firebase/auth";
import { GoogleLogoIcon } from "@phosphor-icons/react";
import { firebaseAuth, googleProvider, FIREBASE_CONFIGURED } from "../lib/firebase";
import { useAuth } from "../auth/AuthContext";
import { Button } from "./ui/Button";

export function GoogleSignInButton({ onDone, onError }: { onDone: () => void; onError: (message: string) => void }) {
  const { loginWithGoogle } = useAuth();
  const [busy, setBusy] = useState(false);

  if (!FIREBASE_CONFIGURED) {
    return (
      <div className="w-full rounded-xl border border-dashed border-white/15 px-4 py-2.5 text-center text-xs text-slate-500">
        Google Sign-In needs Firebase config (VITE_FIREBASE_API_KEY / VITE_FIREBASE_PROJECT_ID) - not configured yet
      </div>
    );
  }

  async function handleClick() {
    setBusy(true);
    try {
      const result = await signInWithPopup(firebaseAuth!, googleProvider);
      const idToken = await result.user.getIdToken();
      await loginWithGoogle(idToken);
      onDone();
    } catch {
      onError("Google sign-in was cancelled or failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Button variant="secondary" fullWidth onClick={handleClick} disabled={busy}>
      <GoogleLogoIcon size={18} weight="bold" />
      {busy ? "Signing in..." : "Continue with Google"}
    </Button>
  );
}
