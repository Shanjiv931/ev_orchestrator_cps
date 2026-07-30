"""Curated catalog of real Indian EV models (public specifications), used to
drive the "pick your vehicle" dropdown instead of forcing every user through
manual connector/chemistry entry. Facts (brand, model, battery chemistry,
usable capacity, connector standard) are not copyrightable; nothing here is
copied text from any manufacturer source, and no logos/trademarked imagery
are used - just plain technical attributes needed for simulation realism.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CatalogEntry:
    brand: str
    vehicle_model: str
    vehicle_class: str  # 2W | 3W | 4W
    connector_type: str
    battery_chemistry: str
    battery_capacity_kwh: float
    is_pluggable: bool = True
    color_hex: str = "#1E293B"


VEHICLE_CATALOG: list[CatalogEntry] = [
    # --- 4-wheelers ---
    CatalogEntry("Tata", "Nexon EV Long Range", "4W", "CCS2", "NMC", 40.5, color_hex="#1D4ED8"),
    CatalogEntry("Tata", "Tiago EV", "4W", "CCS2", "LFP", 24.0, color_hex="#DC2626"),
    CatalogEntry("Tata", "Punch EV", "4W", "CCS2", "LFP", 35.0, color_hex="#059669"),
    CatalogEntry("Tata", "Tigor EV", "4W", "CCS2", "NMC", 26.0, color_hex="#7C3AED"),
    CatalogEntry("MG", "ZS EV", "4W", "CCS2", "NMC", 50.3, color_hex="#EA580C"),
    CatalogEntry("MG", "Comet EV", "4W", "CCS2", "LFP", 17.3, color_hex="#0891B2"),
    CatalogEntry("MG", "Windsor EV", "4W", "CCS2", "LFP", 38.0, color_hex="#4338CA"),
    CatalogEntry("Hyundai", "Kona Electric", "4W", "CCS2", "NMC", 39.2, color_hex="#111827"),
    CatalogEntry("Hyundai", "Ioniq 5", "4W", "CCS2", "NMC", 72.6, color_hex="#F8FAFC"),
    CatalogEntry("Kia", "EV6", "4W", "CCS2", "NMC", 77.4, color_hex="#334155"),
    CatalogEntry("Mahindra", "XUV400", "4W", "CCS2", "NMC", 39.4, color_hex="#B91C1C"),
    CatalogEntry("Mahindra", "BE 6", "4W", "CCS2", "NMC", 79.0, color_hex="#1E293B"),
    CatalogEntry("BYD", "Atto 3", "4W", "CCS2", "LFP", 60.5, color_hex="#16A34A"),
    CatalogEntry("BYD", "e6", "4W", "CCS2", "LFP", 71.7, color_hex="#0F766E"),
    CatalogEntry("Citroen", "eC3", "4W", "CCS2", "LFP", 29.2, color_hex="#EAB308"),
    CatalogEntry("BMW", "i4", "4W", "CCS2", "NMC", 83.9, color_hex="#1C1917"),
    CatalogEntry("Mercedes-Benz", "EQB", "4W", "CCS2", "NMC", 66.5, color_hex="#94A3B8"),
    # --- 3-wheelers ---
    CatalogEntry("Mahindra", "Treo", "3W", "Bharat AC-001", "LFP", 7.4, color_hex="#059669"),
    CatalogEntry("Piaggio", "Ape E-City", "3W", "Bharat AC-001", "lead-acid", 7.2, color_hex="#F59E0B"),
    CatalogEntry("Bajaj", "RE EV", "3W", "Bharat AC-001", "LFP", 8.0, color_hex="#2563EB"),
    CatalogEntry("Euler Motors", "HiLoad EV", "3W", "swap-cassette", "LFP", 12.4, color_hex="#DC2626"),
    # --- 2-wheelers ---
    CatalogEntry("Ola Electric", "S1 Pro", "2W", "Bharat AC-001", "LFP", 4.0, color_hex="#111827"),
    CatalogEntry("Ola Electric", "S1 Air", "2W", "Bharat AC-001", "LFP", 3.0, color_hex="#DC2626"),
    CatalogEntry("Ather", "450X", "2W", "Bharat AC-001", "LFP", 3.7, color_hex="#0891B2"),
    CatalogEntry("Ather", "450 Apex", "2W", "Bharat AC-001", "LFP", 3.7, color_hex="#7C3AED"),
    CatalogEntry("TVS", "iQube", "2W", "Bharat AC-001", "LFP", 3.4, color_hex="#1D4ED8"),
    CatalogEntry("Bajaj", "Chetak", "2W", "Bharat AC-001", "LFP", 3.0, color_hex="#059669"),
    CatalogEntry("Hero", "Vida V1", "2W", "Bharat AC-001", "LFP", 3.44, color_hex="#EA580C"),
    CatalogEntry("Simple Energy", "Simple One", "2W", "Bharat AC-001", "LFP", 4.8, color_hex="#4338CA"),
    CatalogEntry("Revolt", "RV400", "2W", "swap-cassette", "LFP", 3.24, color_hex="#B91C1C"),
]


def find_entry(brand: str, vehicle_model: str) -> CatalogEntry | None:
    for entry in VEHICLE_CATALOG:
        if entry.brand == brand and entry.vehicle_model == vehicle_model:
            return entry
    return None
