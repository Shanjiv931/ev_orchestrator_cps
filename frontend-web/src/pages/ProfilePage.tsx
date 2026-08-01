import { useEffect, useState } from "react";
import {
  UserCircleIcon, LockKeyIcon, CarIcon, CheckCircleIcon,
} from "@phosphor-icons/react";
import { api, ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import type { Vehicle } from "../api/types";
import { GlassCard } from "../components/ui/GlassCard";
import { Button } from "../components/ui/Button";
import { Input, FieldLabel } from "../components/ui/Input";

type Tab = "profile" | "password" | "vehicles";

const TABS: { id: Tab; label: string; icon: typeof UserCircleIcon }[] = [
  { id: "profile", label: "View Profile", icon: UserCircleIcon },
  { id: "password", label: "Change Password", icon: LockKeyIcon },
  { id: "vehicles", label: "Vehicle Details", icon: CarIcon },
];

export function ProfilePage() {
  const [tab, setTab] = useState<Tab>("profile");

  return (
    <div className="pb-4 max-w-lg mx-auto">
      <div className="flex items-center gap-2 mb-4">
        <UserCircleIcon size={24} weight="duotone" className="text-emerald-400" />
        <h1 className="font-display text-2xl font-bold">My profile</h1>
      </div>

      <div className="flex gap-1.5 mb-4 overflow-x-auto">
        {TABS.map(({ id, label, icon: Icon }) => (
          <button key={id} onClick={() => setTab(id)}
                  className={`shrink-0 text-xs px-3 py-1.5 rounded-lg cursor-pointer transition-colors inline-flex items-center gap-1.5 ${
                    tab === id ? "bg-emerald-500/20 text-emerald-300" : "text-slate-400 hover:bg-white/5"
                  }`}>
            <Icon size={14} /> {label}
          </button>
        ))}
      </div>

      {tab === "profile" && <ViewProfileTab />}
      {tab === "password" && <ChangePasswordTab />}
      {tab === "vehicles" && <VehicleDetailsTab />}
    </div>
  );
}

function ViewProfileTab() {
  const { user, updateProfile } = useAuth();
  const [name, setName] = useState(user?.name ?? "");
  const [phoneNumber, setPhoneNumber] = useState(user?.phone_number ?? "");
  const [profession, setProfession] = useState(user?.profession ?? "");
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function save() {
    setBusy(true);
    setError(null);
    setSaved(false);
    try {
      await updateProfile({ name, phoneNumber, profession });
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not update profile.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <GlassCard className="flex flex-col gap-3">
      <div>
        <FieldLabel>Full name</FieldLabel>
        <Input value={name} onChange={(e) => setName(e.target.value)} />
      </div>
      <div>
        <FieldLabel>Email</FieldLabel>
        <Input value={user?.email ?? ""} disabled className="opacity-60" />
        <p className="text-[10px] text-slate-500 mt-1">Email can't be changed - it's your account's sign-in identity.</p>
      </div>
      <div>
        <FieldLabel>Phone number</FieldLabel>
        <Input value={phoneNumber} onChange={(e) => setPhoneNumber(e.target.value)} type="tel" />
      </div>
      <div>
        <FieldLabel>Date of birth</FieldLabel>
        <Input value={user?.date_of_birth ?? ""} disabled className="opacity-60" />
      </div>
      <div>
        <FieldLabel>Profession</FieldLabel>
        <Input value={profession} onChange={(e) => setProfession(e.target.value)} />
      </div>
      <div>
        <FieldLabel>License number</FieldLabel>
        <Input value={user?.license_number ?? ""} disabled className="opacity-60" />
      </div>
      <div>
        <FieldLabel>Location</FieldLabel>
        <Input value={[user?.location_city, user?.location_state].filter(Boolean).join(", ")} disabled className="opacity-60" />
      </div>

      {error && <p className="text-red-400 text-xs">{error}</p>}
      {saved && (
        <p className="text-emerald-400 text-xs flex items-center gap-1"><CheckCircleIcon size={14} weight="fill" /> Profile updated.</p>
      )}
      <Button onClick={save} disabled={busy || !name.trim()}>{busy ? "Saving..." : "Update profile"}</Button>
    </GlassCard>
  );
}

function ChangePasswordTab() {
  const { user, changePassword } = useAuth();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  if (user && user.auth_provider !== "password") {
    return (
      <GlassCard>
        <p className="text-sm text-slate-400">
          This account signs in via {user.auth_provider === "google" ? "Google" : user.auth_provider} - there's no
          password to change here.
        </p>
      </GlassCard>
    );
  }

  async function submit() {
    setError(null);
    if (newPassword !== confirmPassword) {
      setError("New passwords don't match.");
      return;
    }
    setBusy(true);
    try {
      await changePassword(currentPassword, newPassword);
      setDone(true);
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not change password.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <GlassCard className="flex flex-col gap-3">
      <div>
        <FieldLabel>Current password</FieldLabel>
        <Input type="password" value={currentPassword} onChange={(e) => setCurrentPassword(e.target.value)} />
      </div>
      <div>
        <FieldLabel>New password</FieldLabel>
        <Input type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} />
      </div>
      <div>
        <FieldLabel>Confirm new password</FieldLabel>
        <Input type="password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} />
      </div>
      {error && <p className="text-red-400 text-xs">{error}</p>}
      {done && (
        <p className="text-emerald-400 text-xs flex items-center gap-1"><CheckCircleIcon size={14} weight="fill" /> Password changed.</p>
      )}
      <Button onClick={submit} disabled={busy || !currentPassword || !newPassword}>
        {busy ? "Updating..." : "Change password"}
      </Button>
    </GlassCard>
  );
}

function VehicleDetailsTab() {
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);

  useEffect(() => {
    api.get<Vehicle[]>("/vehicles").then(setVehicles).catch(() => setVehicles([]));
  }, []);

  if (vehicles.length === 0) {
    return <GlassCard><p className="text-sm text-slate-500">No vehicles registered yet - add one from the Vehicles page.</p></GlassCard>;
  }

  return (
    <div className="flex flex-col gap-3">
      {vehicles.map((v) => (
        <GlassCard key={v.id}>
          <p className="font-medium">{v.brand ? `${v.brand} ${v.vehicle_model}` : v.vehicle_class}</p>
          {v.number_plate && <p className="text-xs font-mono text-slate-400 mt-0.5">{v.number_plate}</p>}
          <div className="grid grid-cols-2 gap-1.5 mt-3 text-xs text-slate-400">
            <span>Class: {v.vehicle_class}</span>
            <span>Connector: {v.connector_type}</span>
            <span>Chemistry: {v.battery_chemistry}</span>
            <span>Capacity: {v.battery_capacity_kwh ? `${v.battery_capacity_kwh} kWh` : "-"}</span>
            <span>Plug-in: {v.is_pluggable ? "Yes" : "No"}</span>
            <span>Paired: {v.is_paired ? "Yes" : "No"}</span>
          </div>
        </GlassCard>
      ))}
    </div>
  );
}
