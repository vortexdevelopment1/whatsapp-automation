from fastapi import APIRouter
from app.api.v1.agents import router as agents_router
from app.api.v1.branding import router as branding_router
from app.api.v1.whatsapp import router as whatsapp_router
from app.api.v1.templates import agent_templates_router, templates_router
from app.api.v1.messages import router as messages_router
from app.api.v1.audit import router as audit_router
from app.api.v1.lead_sources import router as lead_sources_router
from app.api.v1.leads import router as leads_router
from app.api.v1.tenant_requirements import router as tenant_requirements_router
from app.api.v1.qualification_rules import router as qualification_rules_router
from app.api.v1.system import router as system_router
from app.api.v1.webhook import router as webhook_router
from app.api.v1.faqs import router as faqs_router
from app.api.v1.properties import router as properties_router
from app.api.v1.property_listings import router as property_listings_router
from app.api.v1.property_sources import router as property_sources_router
from app.api.v1.property_agents import router as property_agents_router
from app.api.v1.property_imports import router as property_imports_router
from app.api.v1.property_duplicate_reviews import router as property_duplicate_reviews_router
from app.api.v1.property_matching import router as property_matching_router
from app.api.v1.property_agent_outreach import router as property_agent_outreach_router
from app.api.v1.property_availability_verification import router as property_availability_verification_router
from app.api.v1.property_agent_followups import router as property_agent_followups_router
from app.api.v1.property_shortlists import router as property_shortlists_router
from app.api.v1.viewings import router as viewings_router
from app.api.v1.property_presentation import router as property_presentation_router
from app.api.v1.viewing_availability import router as viewing_availability_router
from app.api.v1.viewing_confirmation import router as viewing_confirmation_router

api_router = APIRouter()
api_router.include_router(agents_router)
api_router.include_router(branding_router)
api_router.include_router(whatsapp_router)
api_router.include_router(agent_templates_router)
api_router.include_router(templates_router)
api_router.include_router(messages_router)
api_router.include_router(audit_router)
api_router.include_router(lead_sources_router)
api_router.include_router(leads_router)
api_router.include_router(tenant_requirements_router)
api_router.include_router(qualification_rules_router)
api_router.include_router(system_router)
api_router.include_router(webhook_router)
api_router.include_router(faqs_router)
api_router.include_router(properties_router)
api_router.include_router(property_listings_router)
api_router.include_router(property_sources_router)
api_router.include_router(property_agents_router)
api_router.include_router(property_imports_router)
api_router.include_router(property_duplicate_reviews_router)
api_router.include_router(property_matching_router)
api_router.include_router(property_agent_outreach_router)
api_router.include_router(property_availability_verification_router)
api_router.include_router(property_agent_followups_router)
api_router.include_router(property_shortlists_router)
api_router.include_router(viewings_router)
api_router.include_router(property_presentation_router)
api_router.include_router(viewing_availability_router)
api_router.include_router(viewing_confirmation_router)








