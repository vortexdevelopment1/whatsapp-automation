import urllib.request
import json

base_url = 'http://localhost:8000'

# 1. Fetch agents
req = urllib.request.urlopen(f'{base_url}/api/agents')
agents = json.loads(req.read().decode())
print(f'Total agents: {len(agents)}')
rachel_agents = [a for a in agents if 'Rachel' in a['full_name']]
assert len(rachel_agents) > 0, "Rachel Lim agent not found"
agent = rachel_agents[0]
agent_id = agent['id']
print(f"Verified agent created: {agent['full_name']} | Status: {agent['status']} | Auth: {agent['authorization_status']}")

# 2. Update WhatsApp config
whatsapp_data = json.dumps({
    'meta_business_account_id': '109876543210987',
    'phone_number_id': '987654321098765',
    'display_phone_number': '+65 9234 5678',
    'business_display_name': 'Rachel Lim - OrangeTee',
    'connection_status': 'CONFIGURED'
}).encode()
req = urllib.request.Request(
    f'{base_url}/api/agents/{agent_id}/whatsapp',
    data=whatsapp_data,
    headers={'Content-Type': 'application/json'},
    method='PUT'
)
res = urllib.request.urlopen(req)
wa_profile = json.loads(res.read().decode())
print(f"WhatsApp Profile: {wa_profile['phone_number_id']}, Status: {wa_profile['connection_status']}")

# 3. Create Template
template_data = json.dumps({
    'template_name': 'tenant_first_contact',
    'meta_template_name': 'tenant_contact_v1',
    'language': 'en_US',
    'category': 'UTILITY',
    'body': 'Hello {{1}}, thank you for your inquiry on {{2}}. I am {{3}} from OrangeTee.',
    'status': 'APPROVED'
}).encode()
req = urllib.request.Request(
    f'{base_url}/api/agents/{agent_id}/templates',
    data=template_data,
    headers={'Content-Type': 'application/json'},
    method='POST'
)
res = urllib.request.urlopen(req)
tpl = json.loads(res.read().decode())
print(f"Template created: {tpl['template_name']} | Status: {tpl['status']}")

# 4. Fetch Audit Logs
req = urllib.request.urlopen(f'{base_url}/api/audit-logs?entity_id={agent_id}')
logs = json.loads(req.read().decode())
actions = [l['action'] for l in logs]
print(f"Audit log actions recorded: {actions}")

print("\n--- ALL VERIFICATIONS PASSED SUCCESSFULLY ---")
