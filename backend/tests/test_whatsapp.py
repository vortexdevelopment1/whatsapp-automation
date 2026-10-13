import uuid
import pytest
from sqlalchemy.exc import IntegrityError
from app.models.enums import WhatsAppConnectionStatus, MessageDirection, MessageType
from app.models.whatsapp import WhatsAppProfile
from app.models.message import WhatsAppMessage


def test_whatsapp_profile_lifecycle(client):
    create_res = client.post(
        "/api/agents",
        json={"full_name": "WhatsApp Agent", "agency_name": "EdgeProp Real Estate"},
    )
    agent_id = create_res.json()["id"]

    # Retrieve auto-created WhatsApp profile
    get_res = client.get(f"/api/agents/{agent_id}/whatsapp")
    assert get_res.status_code == 200
    profile = get_res.json()
    assert profile["connection_status"] == WhatsAppConnectionStatus.NOT_CONFIGURED.value
    assert profile["webhook_verified"] is False
    assert "token" not in profile  # Guarantee no token field exposed

    # Update WhatsApp profile credentials (account ID, phone ID, display phone)
    update_payload = {
        "meta_business_account_id": "meta_biz_12345678",
        "phone_number_id": "phone_num_987654321",
        "display_phone_number": "+65 9876 5432",
        "business_display_name": "EdgeProp Verified Agent",
        "connection_status": WhatsAppConnectionStatus.CONFIGURED.value,
    }
    put_res = client.put(f"/api/agents/{agent_id}/whatsapp", json=update_payload)
    assert put_res.status_code == 200
    updated = put_res.json()
    assert updated["meta_business_account_id"] == "meta_biz_12345678"
    assert updated["phone_number_id"] == "phone_num_987654321"
    assert updated["connection_status"] == WhatsAppConnectionStatus.CONFIGURED.value


def test_unique_provider_message_id_and_foreign_key(db, client):
    # Create agent & get profile id
    create_res = client.post(
        "/api/agents",
        json={"full_name": "Message Agent", "agency_name": "ERA Realty"},
    )
    agent_id = create_res.json()["id"]
    get_res = client.get(f"/api/agents/{agent_id}/whatsapp")
    profile_id = uuid.UUID(get_res.json()["id"])

    # Insert first message with a provider_message_id
    msg1 = WhatsAppMessage(
        whatsapp_profile_id=profile_id,
        provider_message_id="wamid.HBgLMTEyMjMzNDQ1NQ==",
        direction=MessageDirection.INBOUND,
        message_type=MessageType.TEXT,
        sender="+6591112222",
        recipient="+6598765432",
        content="Hello, inquiring about the unit.",
    )
    db.add(msg1)
    db.commit()

    # Attempt to insert duplicate provider_message_id - must trigger IntegrityError
    msg2 = WhatsAppMessage(
        whatsapp_profile_id=profile_id,
        provider_message_id="wamid.HBgLMTEyMjMzNDQ1NQ==",
        direction=MessageDirection.INBOUND,
        message_type=MessageType.TEXT,
        sender="+6591112222",
        recipient="+6598765432",
        content="Duplicate message arrival.",
    )
    db.add(msg2)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_foreign_key_constraint_invalid_profile(db):
    # Attempt to insert message with non-existent whatsapp_profile_id
    invalid_profile_id = uuid.uuid4()
    msg = WhatsAppMessage(
        whatsapp_profile_id=invalid_profile_id,
        provider_message_id="wamid.random123",
        direction=MessageDirection.OUTBOUND,
        message_type=MessageType.TEXT,
        sender="+6598765432",
        recipient="+6591112222",
        content="Test outbound",
    )
    db.add(msg)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
