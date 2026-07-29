import pytest

from ml.carbon_ledger import compute_carbon_impact


def test_carbon_impact_scales_with_energy():
    small = compute_carbon_impact(energy_kwh=5.0, vehicle_class="4W")
    large = compute_carbon_impact(energy_kwh=50.0, vehicle_class="4W")
    assert large.co2_avoided_kg > small.co2_avoided_kg


def test_carbon_impact_is_positive_for_a_typical_session():
    impact = compute_carbon_impact(energy_kwh=12.0, vehicle_class="4W")
    assert impact.co2_avoided_kg > 0
    assert impact.equivalent_fuel_baseline == "petrol 4W"


def test_unknown_vehicle_class_raises():
    with pytest.raises(ValueError):
        compute_carbon_impact(energy_kwh=10.0, vehicle_class="spaceship")


def test_2w_and_4w_have_different_equivalence_baselines_for_the_same_energy():
    result_2w = compute_carbon_impact(energy_kwh=3.0, vehicle_class="2W")
    result_4w = compute_carbon_impact(energy_kwh=3.0, vehicle_class="4W")
    assert result_2w.equivalent_fuel_baseline != result_4w.equivalent_fuel_baseline
    assert result_2w.distance_km_equivalent != result_4w.distance_km_equivalent
