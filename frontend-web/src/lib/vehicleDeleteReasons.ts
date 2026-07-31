// Mirrors backend/app/vellore.py's DELETE_REASON_CODES exactly - kept as a
// plain literal list rather than fetched from the API since it almost never
// changes and every consumer already imports the backend's Vehicle types
// directly from this same frontend package.
export interface DeleteReasonOption {
  code: string;
  label: string;
}

export const DELETE_REASON_OPTIONS: DeleteReasonOption[] = [
  { code: "sold_or_transferred", label: "Sold or transferred to someone else" },
  { code: "vehicle_damaged_or_totaled", label: "Vehicle damaged or totaled" },
  { code: "replacing_with_different_vehicle", label: "Replacing with a different vehicle" },
  { code: "duplicate_registration", label: "Registered by mistake / duplicate" },
  { code: "other", label: "Other" },
];
