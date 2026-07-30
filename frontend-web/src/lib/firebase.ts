/**
 * Firebase is used for exactly one thing here: its Google sign-in popup and
 * ID token. No Firestore/Realtime Database/Analytics - this project's own
 * FastAPI backend and Postgres remain the actual data store, verified via
 * `verify_firebase_token` (see backend/app/routers/oauth.py), which needs
 * only the project ID, not a service-account key.
 */
import { initializeApp, type FirebaseOptions } from "firebase/app";
import { getAuth, GoogleAuthProvider } from "firebase/auth";

const firebaseConfig: FirebaseOptions = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
};

export const FIREBASE_CONFIGURED = Boolean(firebaseConfig.apiKey && firebaseConfig.projectId);

export const firebaseAuth = FIREBASE_CONFIGURED ? getAuth(initializeApp(firebaseConfig)) : null;
export const googleProvider = new GoogleAuthProvider();
