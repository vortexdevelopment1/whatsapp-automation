def test_audit_logs_created_on_agent_actions(client):
    # 1. Create agent
    res = client.post(
        "/api/agents",
        json={"full_name": "Audited Agent", "agency_name": "Audit Real Estate"},
    )
    agent_id = res.json()["id"]

    # 2. Update agent
    client.patch(
        f"/api/agents/{agent_id}",
        json={"notes": "Audit log trigger note"},
    )

    # 3. Retrieve audit logs
    logs_res = client.get(f"/api/audit-logs?entity_id={agent_id}")
    assert logs_res.status_code == 200
    logs = logs_res.json()
    assert len(logs) >= 2

    actions = [l["action"] for l in logs]
    assert "AGENT_CREATED" in actions
    assert "AGENT_UPDATED" in actions
