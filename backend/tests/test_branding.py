import uuid
from app.models.enums import BrandingStatus


def test_branding_lifecycle(client):
    create_res = client.post(
        "/api/agents",
        json={"full_name": "Branding Agent", "agency_name": "Luxury Estates"},
    )
    agent_id = create_res.json()["id"]

    # Retrieve default branding profile
    get_res = client.get(f"/api/agents/{agent_id}/branding")
    assert get_res.status_code == 200
    branding = get_res.json()
    assert branding["branding_status"] == BrandingStatus.NOT_STARTED.value
    assert branding["agent_id"] == agent_id

    # Update branding details
    update_payload = {
        "business_description": "Premier luxury residential specialist in District 9/10.",
        "office_address": "123 Marina Bay Boulevard, #18-01, Singapore",
        "website": "https://luxuryestates.example.com/branding-agent",
        "branding_status": BrandingStatus.READY.value,
    }
    put_res = client.put(f"/api/agents/{agent_id}/branding", json=update_payload)
    assert put_res.status_code == 200
    updated = put_res.json()
    assert updated["business_description"] == update_payload["business_description"]
    assert updated["website"] == update_payload["website"]
    assert updated["branding_status"] == BrandingStatus.READY.value


def test_branding_nonexistent_agent(client):
    random_id = uuid.uuid4()
    get_res = client.get(f"/api/agents/{random_id}/branding")
    assert get_res.status_code == 404
