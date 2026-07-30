import { useState } from "react";
import { FlaskIcon } from "@phosphor-icons/react";
import { useAuth } from "../auth/AuthContext";
import { Button } from "./ui/Button";

/** Deliberately simulated - see docs/out-of-scope.md. No Apple branding is
 * used here (this is not a real "Sign in with Apple" button, and must
 * never look like one) since Sign in with Apple requires a paid Apple
 * Developer account this project doesn't have. */
export function AppleSignInButtonSimulated({ onDone, onError }: { onDone: () => void; onError: (message: string) => void }) {
  const { loginWithSimulatedApple } = useAuth();
  const [busy, setBusy] = useState(false);

  async function handleClick() {
    setBusy(true);
    try {
      const demoId = crypto.randomUUID();
      await loginWithSimulatedApple(demoId, "Simulated Apple User");
      onDone();
    } catch {
      onError("Simulated Apple sign-in failed unexpectedly");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Button variant="ghost" fullWidth onClick={handleClick} disabled={busy}>
      <FlaskIcon size={18} weight="duotone" />
      Continue with Apple <span className="text-slate-500">(simulated demo)</span>
    </Button>
  );
}
