def test_list_catalog_returns_real_indian_ev_models(client):
    response = client.get("/vehicle-catalog")
    assert response.status_code == 200
    catalog = response.json()
    assert len(catalog) > 15
    brands = {entry["brand"] for entry in catalog}
    assert "Tata" in brands
    assert "Ather" in brands


def test_catalog_entries_have_valid_connector_chemistry_and_class(client):
    response = client.get("/vehicle-catalog")
    valid_connectors = {"Bharat AC-001", "Bharat DC-001", "CCS2", "Type 2", "swap-cassette"}
    valid_chemistries = {"LFP", "NMC", "lead-acid"}
    for entry in response.json():
        assert entry["connector_type"] in valid_connectors
        assert entry["battery_chemistry"] in valid_chemistries
        assert entry["vehicle_class"] in {"2W", "3W", "4W"}
        assert entry["battery_capacity_kwh"] > 0
