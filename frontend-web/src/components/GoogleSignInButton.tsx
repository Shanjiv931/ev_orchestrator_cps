import { GoogleLogin } from "@react-oauth/google";
import { useAuth } from "../auth/AuthContext";

const CONFIGURED = Boolean(import.meta.env.VITE_GOOGLE_OAUTH_CLIENT_ID);

export function GoogleSignInButton({ onDone, onError }: { onDone: () => void; onError: (message: string) => void }) {
  const { loginWithGoogle } = useAuth();

  if (!CONFIGURED) {
    return (
      <div className="w-full rounded-xl border border-dashed border-white/15 px-4 py-2.5 text-center text-xs text-slate-500">
        Google Sign-In needs a Client ID (VITE_GOOGLE_OAUTH_CLIENT_ID) - not configured yet
      </div>
    );
  }

  return (
    <div className="flex justify-center [&>div]:w-full">
      <GoogleLogin
        onSuccess={async (credentialResponse) => {
          if (!credentialResponse.credential) {
            onError("Google did not return a credential");
            return;
          }
          try {
            await loginWithGoogle(credentialResponse.credential);
            onDone();
          } catch {
            onError("Google sign-in failed on the server");
          }
        }}
        onError={() => onError("Google sign-in was cancelled or failed")}
        theme="filled_black"
        shape="pill"
        width="320"
      />
    </div>
  );
}
