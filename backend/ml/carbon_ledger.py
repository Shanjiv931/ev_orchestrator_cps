"""Carbon/ESG tracking (Section 5.10).

Computes CO2 avoided for a completed charging session versus an equivalent
petrol/diesel trip, using established well-to-wheel figures, so fleet
operators get a concrete, exportable sustainability number.

Figures used (India-representative, well-to-wheel):
- Grid emission factor: ~0.82 kg CO2/kWh (CEA baseline database, all-India).
- Petrol ICE well-to-wheel: ~2.31 kg CO2/litre; a typical 4W does ~15 km/litre.
- 2W/3W ICE well-to-wheel equivalents are computed per-km instead, since a
  litres-per-charge figure doesn't map cleanly onto a 2W/3W trip.
"""
from __future__ import annotations

from dataclasses import dataclass

GRID_EMISSION_FACTOR_KG_PER_KWH = 0.82
PETROL_WELL_TO_WHEEL_KG_PER_LITRE = 2.31
PETROL_4W_KM_PER_LITRE = 15.0
PETROL_2W_KM_PER_LITRE = 45.0
PETROL_3W_KM_PER_LITRE = 25.0

CONSUMPTION_KWH_PER_KM = {"2W": 0.03, "3W": 0.06, "4W": 0.15}
PETROL_KM_PER_LITRE = {"2W": PETROL_2W_KM_PER_LITRE, "3W": PETROL_3W_KM_PER_LITRE, "4W": PETROL_4W_KM_PER_LITRE}


@dataclass
class CarbonImpact:
    co2_avoided_kg: float
    equivalent_fuel_baseline: str
    distance_km_equivalent: float


def compute_carbon_impact(energy_kwh: float, vehicle_class: str) -> CarbonImpact:
    if vehicle_class not in CONSUMPTION_KWH_PER_KM:
        raise ValueError(f"unknown vehicle_class: {vehicle_class}")

    ev_emissions_kg = energy_kwh * GRID_EMISSION_FACTOR_KG_PER_KWH
    distance_km = energy_kwh / CONSUMPTION_KWH_PER_KM[vehicle_class]
    petrol_litres_equivalent = distance_km / PETROL_KM_PER_LITRE[vehicle_class]
    petrol_emissions_kg = petrol_litres_equivalent * PETROL_WELL_TO_WHEEL_KG_PER_LITRE

    co2_avoided_kg = max(0.0, petrol_emissions_kg - ev_emissions_kg)
    return CarbonImpact(
        co2_avoided_kg=round(co2_avoided_kg, 4),
        equivalent_fuel_baseline=f"petrol {vehicle_class}",
        distance_km_equivalent=round(distance_km, 2),
    )
