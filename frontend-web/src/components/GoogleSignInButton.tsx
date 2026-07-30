import { useState } from "react";
import { FirebaseError } from "firebase/app";
import { signInWithPopup } from "firebase/auth";
import { GoogleLogoIcon } from "@phosphor-icons/react";
import { firebaseAuth, googleProvider, FIREBASE_CONFIGURED } from "../lib/firebase";
import { useAuth } from "../auth/AuthContext";
import { Button } from "./ui/Button";

// A bare "cancelled or failed" swallowed the actual Firebase error code,
// which is exactly the info needed to tell "you closed the popup" apart
// from "this domain isn't authorized" or "the Google provider isn't
// enabled on this Firebase project" - all of which look identical to a
// user with no other clue. See https://firebase.google.com/docs/auth/admin/errors
const FIREBASE_ERROR_MESSAGES: Record<string, string> = {
  "auth/popup-closed-by-user": "Sign-in popup was closed before completing",
  "auth/popup-blocked": "Your browser blocked the sign-in popup - allow popups for this site and try again",
  "auth/cancelled-popup-request": "Sign-in was cancelled",
  "auth/unauthorized-domain": "This domain isn't authorized in Firebase - add it under Authentication > Settings > Authorized domains",
  "auth/operation-not-allowed": "Google sign-in isn't enabled on this Firebase project - enable it under Authentication > Sign-in method",
  "auth/network-request-failed": "Network error reaching Firebase - check your connection and try again",
};

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
    } catch (error) {
      console.error("Google sign-in failed:", error);
      const code = error instanceof FirebaseError ? error.code : null;
      onError(
        (code && FIREBASE_ERROR_MESSAGES[code]) ??
          (code ? `Google sign-in failed (${code})` : "Google sign-in failed on the server"),
      );
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
