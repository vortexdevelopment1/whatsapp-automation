import pytest
from app.models.enums import AgentStatus, AuthorizationStatus


def test_create_agent_success(client):
    payload = {
        "full_name": "Sarah Tan",
        "display_name": "Sarah",
        "agency_name": "PropNex Realty",
        "designation": "Associate Senior Director",
        "registration_number": "R012345A",
        "phone": "+65 9123 4567",
        "email": "sarah.tan@example.com",
        "profile_photo_url": "https://example.com/sarah.jpg",
        "notes": "Top producer 2024",
    }
    response = client.post("/api/agents", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["full_name"] == "Sarah Tan"
    assert data["status"] == AgentStatus.DRAFT.value
    assert data["authorization_status"] == AuthorizationStatus.PENDING.value
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


def test_create_agent_validation_errors(client):
    # Missing required full_name and agency_name
    response = client.post("/api/agents", json={})
    assert response.status_code == 422

    # Invalid email
    response = client.post(
        "/api/agents",
        json={
            "full_name": "John Doe",
            "agency_name": "ERA Realty",
            "email": "not-an-email",
        },
    )
    assert response.status_code == 422

    # Invalid phone format
    response = client.post(
        "/api/agents",
        json={
            "full_name": "John Doe",
            "agency_name": "ERA Realty",
            "phone": "invalid_phone_#@!",
        },
    )
    assert response.status_code == 422


def test_update_agent(client):
    create_res = client.post(
        "/api/agents",
        json={
            "full_name": "Alex Wong",
            "agency_name": "Huttons Asia",
            "phone": "+65 8234 5678",
            "email": "alex.wong@example.com",
        },
    )
    agent_id = create_res.json()["id"]

    update_res = client.patch(
        f"/api/agents/{agent_id}",
        json={"display_name": "Alex W", "notes": "Updated notes"},
    )
    assert update_res.status_code == 200
    updated_data = update_res.json()
    assert updated_data["display_name"] == "Alex W"
    assert updated_data["notes"] == "Updated notes"


def test_agent_activation_guard(client):
    # Create agent (default authorization_status = PENDING)
    create_res = client.post(
        "/api/agents",
        json={
            "full_name": "Michael Lee",
            "agency_name": "OrangeTee",
            "email": "michael.lee@example.com",
        },
    )
    agent_id = create_res.json()["id"]

    # Attempt to activate while PENDING - must fail with 400
    activate_res = client.post(f"/api/agents/{agent_id}/activate")
    assert activate_res.status_code == 400
    assert "authorization status must be VERIFIED" in activate_res.json()["detail"]

    # Verify authorization
    patch_res = client.patch(
        f"/api/agents/{agent_id}",
        json={"authorization_status": AuthorizationStatus.VERIFIED.value},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["authorization_status"] == AuthorizationStatus.VERIFIED.value

    # Now activate agent - should succeed
    activate_res2 = client.post(f"/api/agents/{agent_id}/activate")
    assert activate_res2.status_code == 200
    assert activate_res2.json()["status"] == AgentStatus.ACTIVE.value

    # Deactivate agent
    deactivate_res = client.post(f"/api/agents/{agent_id}/deactivate")
    assert deactivate_res.status_code == 200
    assert deactivate_res.json()["status"] == AgentStatus.INACTIVE.value


def test_agent_archive(client):
    create_res = client.post(
        "/api/agents",
        json={
            "full_name": "David Tan",
            "agency_name": "Knight Frank",
            "email": "david.tan@example.com",
        },
    )
    agent_id = create_res.json()["id"]

    archive_res = client.post(f"/api/agents/{agent_id}/archive")
    assert archive_res.status_code == 200
    assert archive_res.json()["status"] == AgentStatus.ARCHIVED.value


def test_list_agents_and_filtering(client):
    client.post(
        "/api/agents",
        json={"full_name": "Filter Test Agent A", "agency_name": "Alpha Properties"},
    )
    client.post(
        "/api/agents",
        json={"full_name": "Filter Test Agent B", "agency_name": "Beta Properties"},
    )

    list_res = client.get("/api/agents?search=Filter%20Test")
    assert list_res.status_code == 200
    items = list_res.json()
    assert len(items) >= 2
