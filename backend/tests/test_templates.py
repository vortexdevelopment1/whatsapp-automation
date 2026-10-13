import uuid
from app.models.enums import TemplateStatus


def test_template_lifecycle(client):
    create_agent_res = client.post(
        "/api/agents",
        json={"full_name": "Template Agent", "agency_name": "Huttons"},
    )
    agent_id = create_agent_res.json()["id"]

    # Create a message template for this agent
    template_payload = {
        "template_name": "rental_intro_greeting",
        "meta_template_name": "rental_intro_v1",
        "language": "en_US",
        "category": "UTILITY",
        "body": "Hi {{1}}, thanks for inquiring about {{2}}. I am {{3}} from {{4}}.",
        "status": TemplateStatus.DRAFT.value,
    }
    create_tpl_res = client.post(f"/api/agents/{agent_id}/templates", json=template_payload)
    assert create_tpl_res.status_code == 201
    tpl_data = create_tpl_res.json()
    assert tpl_data["template_name"] == "rental_intro_greeting"
    assert tpl_data["status"] == TemplateStatus.DRAFT.value
    template_id = tpl_data["id"]

    # List templates for agent
    list_res = client.get(f"/api/agents/{agent_id}/templates")
    assert list_res.status_code == 200
    templates = list_res.json()
    assert any(t["id"] == template_id for t in templates)

    # Update template
    patch_res = client.patch(
        f"/api/templates/{template_id}",
        json={"status": TemplateStatus.APPROVED.value},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["status"] == TemplateStatus.APPROVED.value
