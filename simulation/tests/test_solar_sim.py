import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from solar_sim import _solar_sites, generation_kw_at


def test_zero_generation_before_sunrise_and_after_sunset():
    assert generation_kw_at(4.0, peak_generation_kw=10.0) == 0.0
    assert generation_kw_at(20.0, peak_generation_kw=10.0) == 0.0


def test_peak_generation_at_solar_noon():
    assert generation_kw_at(12.0, peak_generation_kw=10.0) == 10.0


def test_generation_rises_then_falls_across_the_day():
    morning = generation_kw_at(8.0, peak_generation_kw=10.0)
    noon = generation_kw_at(12.0, peak_generation_kw=10.0)
    evening = generation_kw_at(16.0, peak_generation_kw=10.0)
    assert morning < noon
    assert evening < noon
    assert morning > 0
    assert evening > 0


def test_only_has_solar_sites_are_registered():
    sites = _solar_sites()
    site_ids = {s.site_id for s in sites}
    assert "station-indiranagar-hsg-01" in site_ids  # has_solar=True
    assert "station-koramangala-dc-01" not in site_ids  # has_solar=False
    for site in sites:
        assert site.peak_generation_kw > 0
