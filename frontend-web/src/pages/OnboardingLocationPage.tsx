import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { MapPinIcon, NavigationArrowIcon } from "@phosphor-icons/react";
import { useAuth } from "../auth/AuthContext";
import { GlassCard } from "../components/ui/GlassCard";
import { Button } from "../components/ui/Button";
import { Select, FieldLabel } from "../components/ui/Input";
import { INDIAN_STATES, findNearestCity } from "../lib/indianLocations";

export function OnboardingLocationPage() {
  const { updateLocation } = useAuth();
  const navigate = useNavigate();
  const states = Object.keys(INDIAN_STATES);
  const [state, setState] = useState(states[0]);
  const [city, setCity] = useState(INDIAN_STATES[states[0]][0].city);
  const [locating, setLocating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function saveAndContinue(selectedState: string, selectedCity: string) {
    const option = INDIAN_STATES[selectedState].find((c) => c.city === selectedCity);
    if (!option) return;
    await updateLocation(selectedState, selectedCity, option.lat, option.lon);
    navigate("/");
  }

  function useCurrentLocation() {
    if (!navigator.geolocation) {
      setError("Geolocation isn't available in this browser");
      return;
    }
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      async (position) => {
        const nearest = findNearestCity(position.coords.latitude, position.coords.longitude);
        setLocating(false);
        if (nearest) {
          await updateLocation(nearest.state, nearest.city, position.coords.latitude, position.coords.longitude);
        } else {
          await updateLocation(state, city, position.coords.latitude, position.coords.longitude);
        }
        navigate("/");
      },
      () => {
        setLocating(false);
        setError("Couldn't get your location - pick your city manually below");
      },
      { timeout: 8000 },
    );
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
          <MapPinIcon size={36} weight="duotone" className="mx-auto text-emerald-400 mb-2" />
          <h1 className="font-display text-xl font-bold">Where are you?</h1>
          <p className="text-sm text-slate-500 mt-1">We'll centre your map and station recommendations here.</p>
        </div>

        <GlassCard className="p-6">
          <Button variant="secondary" fullWidth onClick={useCurrentLocation} disabled={locating}>
            <NavigationArrowIcon size={18} weight="fill" />
            {locating ? "Locating..." : "Use my current location"}
          </Button>

          <div className="flex items-center gap-3 my-4">
            <div className="h-px flex-1 bg-white/10" />
            <span className="text-xs text-slate-500">or choose manually</span>
            <div className="h-px flex-1 bg-white/10" />
          </div>

          <div className="flex flex-col gap-3">
            <div>
              <FieldLabel>State</FieldLabel>
              <Select value={state} onChange={(e) => {
                const newState = e.target.value;
                setState(newState);
                setCity(INDIAN_STATES[newState][0].city);
              }}>
                {states.map((s) => <option key={s} value={s} className="bg-slate-900">{s}</option>)}
              </Select>
            </div>
            <div>
              <FieldLabel>City</FieldLabel>
              <Select value={city} onChange={(e) => setCity(e.target.value)}>
                {INDIAN_STATES[state].map((c) => (
                  <option key={c.city} value={c.city} className="bg-slate-900">{c.city}</option>
                ))}
              </Select>
            </div>
            {error && <p className="text-amber-400 text-sm">{error}</p>}
            <Button fullWidth onClick={() => saveAndContinue(state, city)}>Continue</Button>
          </div>
        </GlassCard>
      </motion.div>
    </div>
  );
}
