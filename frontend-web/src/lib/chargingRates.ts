export type ChargerType = "AC" | "DC";

// Representative power used for pre-selection time/cost estimates - the
// actual charger assigned on arrival may differ slightly, but this is what
// lets a user compare options before committing.
export const REPRESENTATIVE_POWER_KW: Record<ChargerType, number> = { AC: 7.4, DC: 60 };

// INR/kWh - DC fast charging commands a premium over slow AC top-ups, same
// spread used across most Indian public charging networks.
export const RATE_PER_KWH: Record<ChargerType, number> = { AC: 8, DC: 18 };
