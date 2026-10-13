import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from sqlalchemy.orm import Session

from app.models.property import Property
from app.models.property_listing import PropertyListing
from app.models.property_source import PropertySource
from app.models.property_agent import PropertyAgent
from app.models.enums import (
    PropertyType,
    PropertyStatus,
    FurnishingType,
    PropertySourceType,
    PropertySourceStatus,
    PropertyAgentStatus,
    PropertyListingStatus,
    ListingAvailabilityStatus,
)
from app.services.phone_service import normalize_phone_number


def seed_property_inventory(db: Session) -> dict:
    """Seed safe synthetic demo properties, sources, agents, and listings for UAT and testing."""
    # 1. Sources
    sources_data = [
        {
            "name": "Demo Portal Inventory",
            "source_type": PropertySourceType.DEMO,
            "external_system_name": "DemoPortal_v1",
            "status": PropertySourceStatus.ACTIVE,
        },
        {
            "name": "Direct Agency Sheet",
            "source_type": PropertySourceType.CSV_IMPORT,
            "external_system_name": "AgencySpreadsheet_2026",
            "status": PropertySourceStatus.ACTIVE,
        },
        {
            "name": "Partner MLS Network",
            "source_type": PropertySourceType.APPROVED_API,
            "external_system_name": "MLS_DirectFeed",
            "status": PropertySourceStatus.ACTIVE,
        },
    ]

    sources_map = {}
    for s_data in sources_data:
        existing = db.query(PropertySource).filter(PropertySource.name == s_data["name"]).first()
        if not existing:
            source = PropertySource(
                name=s_data["name"],
                source_type=s_data["source_type"],
                external_system_name=s_data["external_system_name"],
                status=s_data["status"],
            )
            db.add(source)
            db.commit()
            db.refresh(source)
            sources_map[s_data["name"]] = source
        else:
            sources_map[s_data["name"]] = existing

    # 2. Property Agents
    agents_data = [
        {
            "full_name": "John Tan",
            "agency_name": "PropNex Realty",
            "registration_number": "R012345A",
            "phone": "+65 9123 4567",
            "email": "john.tan@propnex-demo.sg",
            "source": "Demo Portal Inventory",
        },
        {
            "full_name": "Mary Lim",
            "agency_name": "ERA Realty Network",
            "registration_number": "R023456B",
            "phone": "+65 9234 5678",
            "email": "mary.lim@era-demo.sg",
            "source": "Direct Agency Sheet",
        },
        {
            "full_name": "David Lee",
            "agency_name": "Huttons Asia",
            "registration_number": "R034567C",
            "phone": "+65 9345 6789",
            "email": "david.lee@huttons-demo.sg",
            "source": "Demo Portal Inventory",
        },
        {
            "full_name": "Sarah Chen",
            "agency_name": "OrangeTee & Tie",
            "registration_number": "R045678D",
            "phone": "+65 9456 7890",
            "email": "sarah.chen@orangetee-demo.sg",
            "source": "Partner MLS Network",
        },
    ]

    agents_map = {}
    for a_data in agents_data:
        norm = normalize_phone_number(a_data["phone"])
        existing = db.query(PropertyAgent).filter(PropertyAgent.phone_normalized == norm).first()
        if not existing:
            agent = PropertyAgent(
                full_name=a_data["full_name"],
                agency_name=a_data["agency_name"],
                registration_number=a_data["registration_number"],
                phone=a_data["phone"],
                phone_normalized=norm,
                email=a_data["email"],
                status=PropertyAgentStatus.ACTIVE,
                source_id=sources_map[a_data["source"]].id,
            )
            db.add(agent)
            db.commit()
            db.refresh(agent)
            agents_map[a_data["full_name"]] = agent
        else:
            agents_map[a_data["full_name"]] = existing

    # 3. Canonical Properties
    props_data = [
        {
            "key": "novena_regency_0804",
            "canonical_name": "Novena Regency #08-04",
            "building_name": "Novena Regency",
            "address_line_1": "275 Thomson Road",
            "unit_number": "#08-04",
            "postal_code": "307645",
            "city": "Singapore",
            "district": "D11 - Novena / Newton",
            "country": "Singapore",
            "property_type": PropertyType.CONDO,
            "bedrooms": 2,
            "bathrooms": Decimal("2.0"),
            "size_sqft": Decimal("850.00"),
            "furnishing": FurnishingType.FURNISHED,
            "status": PropertyStatus.ACTIVE,
            "latitude": Decimal("1.3175000"),
            "longitude": Decimal("103.8436000"),
        },
        {
            "key": "newton_suites_1502",
            "canonical_name": "Newton Suites #15-02",
            "building_name": "Newton Suites",
            "address_line_1": "60 Newton Road",
            "unit_number": "#15-02",
            "postal_code": "307994",
            "city": "Singapore",
            "district": "D11 - Novena / Newton",
            "country": "Singapore",
            "property_type": PropertyType.CONDO,
            "bedrooms": 3,
            "bathrooms": Decimal("3.0"),
            "size_sqft": Decimal("1250.00"),
            "furnishing": FurnishingType.PARTIALLY_FURNISHED,
            "status": PropertyStatus.ACTIVE,
            "latitude": Decimal("1.3142000"),
            "longitude": Decimal("103.8398000"),
        },
        {
            "key": "tanjong_pagar_12108",
            "canonical_name": "Tanjong Pagar Plaza #12-108",
            "building_name": "Tanjong Pagar Plaza",
            "address_line_1": "1 Tanjong Pagar Plaza",
            "unit_number": "#12-108",
            "postal_code": "082001",
            "city": "Singapore",
            "district": "D02 - Chinatown / Tanjong Pagar",
            "country": "Singapore",
            "property_type": PropertyType.HDB,
            "bedrooms": 2,
            "bathrooms": Decimal("1.0"),
            "size_sqft": Decimal("700.00"),
            "furnishing": FurnishingType.UNFURNISHED,
            "status": PropertyStatus.ACTIVE,
            "latitude": Decimal("1.2764000"),
            "longitude": Decimal("103.8432000"),
        },
        {
            "key": "orchard_scotts_0501",
            "canonical_name": "Orchard Scotts #05-01",
            "building_name": "Orchard Scotts",
            "address_line_1": "20 Anthony Road",
            "unit_number": "#05-01",
            "postal_code": "229956",
            "city": "Singapore",
            "district": "D09 - Orchard / River Valley",
            "country": "Singapore",
            "property_type": PropertyType.CONDO,
            "bedrooms": 4,
            "bathrooms": Decimal("4.0"),
            "size_sqft": Decimal("2100.00"),
            "furnishing": FurnishingType.FURNISHED,
            "status": PropertyStatus.ACTIVE,
            "latitude": Decimal("1.3108000"),
            "longitude": Decimal("103.8378000"),
        },
        {
            "key": "bishan_loft_1806",
            "canonical_name": "Bishan Loft #18-06",
            "building_name": "Bishan Loft",
            "address_line_1": "33 Bishan Street 21",
            "unit_number": "#18-06",
            "postal_code": "579800",
            "city": "Singapore",
            "district": "D20 - Ang Mo Kio / Bishan",
            "country": "Singapore",
            "property_type": PropertyType.CONDO,
            "bedrooms": 3,
            "bathrooms": Decimal("2.0"),
            "size_sqft": Decimal("1100.00"),
            "furnishing": FurnishingType.FURNISHED,
            "status": PropertyStatus.ACTIVE,
            "latitude": Decimal("1.3524000"),
            "longitude": Decimal("103.8490000"),
        },
    ]

    props_map = {}
    for p_data in props_data:
        existing = db.query(Property).filter(Property.canonical_name == p_data["canonical_name"]).first()
        if not existing:
            prop = Property(
                canonical_name=p_data["canonical_name"],
                building_name=p_data["building_name"],
                address_line_1=p_data["address_line_1"],
                unit_number=p_data["unit_number"],
                postal_code=p_data["postal_code"],
                city=p_data["city"],
                district=p_data["district"],
                country=p_data["country"],
                property_type=p_data["property_type"],
                bedrooms=p_data["bedrooms"],
                bathrooms=p_data["bathrooms"],
                size_sqft=p_data["size_sqft"],
                furnishing=p_data["furnishing"],
                status=p_data["status"],
                latitude=p_data["latitude"],
                longitude=p_data["longitude"],
            )
            db.add(prop)
            db.commit()
            db.refresh(prop)
            props_map[p_data["key"]] = prop
        else:
            props_map[p_data["key"]] = existing

    # 4. Property Listings
    # Property A (Novena Regency #08-04) gets TWO listings:
    # Listing 1: SGD 3500 from Demo Portal (Agent John Tan) - UNKNOWN availability
    # Listing 2: SGD 3650 from Direct Agency Sheet (Agent Mary Lim) - AVAILABLE
    listings_data = [
        {
            "property_key": "novena_regency_0804",
            "source_name": "Demo Portal Inventory",
            "agent_name": "John Tan",
            "source_listing_id": "NOV-DEMO-001",
            "source_url": "https://example-demo-portal.sg/listings/NOV-DEMO-001",
            "asking_price": Decimal("3500.00"),
            "currency": "SGD",
            "availability_status": ListingAvailabilityStatus.UNKNOWN,
            "available_from": date(2026, 12, 1),
            "lease_min_months": 12,
            "lease_max_months": 24,
            "listing_status": PropertyListingStatus.ACTIVE,
        },
        {
            "property_key": "novena_regency_0804",
            "source_name": "Direct Agency Sheet",
            "agent_name": "Mary Lim",
            "source_listing_id": "ERA-SHEET-902",
            "source_url": "https://example-agency.sg/listings/ERA-SHEET-902",
            "asking_price": Decimal("3650.00"),
            "currency": "SGD",
            "availability_status": ListingAvailabilityStatus.AVAILABLE,
            "available_from": date(2026, 11, 15),
            "lease_min_months": 12,
            "lease_max_months": 12,
            "listing_status": PropertyListingStatus.ACTIVE,
            "last_verified_at": datetime.now(timezone.utc),
        },
        {
            "property_key": "newton_suites_1502",
            "source_name": "Demo Portal Inventory",
            "agent_name": "David Lee",
            "source_listing_id": "NEWTON-DEMO-002",
            "source_url": "https://example-demo-portal.sg/listings/NEWTON-DEMO-002",
            "asking_price": Decimal("5800.00"),
            "currency": "SGD",
            "availability_status": ListingAvailabilityStatus.NOT_CHECKED,
            "available_from": date(2026, 11, 1),
            "lease_min_months": 12,
            "lease_max_months": None,
            "listing_status": PropertyListingStatus.ACTIVE,
        },
        {
            "property_key": "tanjong_pagar_12108",
            "source_name": "Partner MLS Network",
            "agent_name": "Sarah Chen",
            "source_listing_id": "MLS-TP-883",
            "source_url": "https://example-mls.sg/listings/MLS-TP-883",
            "asking_price": Decimal("2800.00"),
            "currency": "SGD",
            "availability_status": ListingAvailabilityStatus.UNAVAILABLE,
            "available_from": date(2027, 1, 1),
            "lease_min_months": 12,
            "lease_max_months": 24,
            "listing_status": PropertyListingStatus.ACTIVE,
        },
        {
            "property_key": "orchard_scotts_0501",
            "source_name": "Demo Portal Inventory",
            "agent_name": "John Tan",
            "source_listing_id": "ORC-DEMO-004",
            "source_url": "https://example-demo-portal.sg/listings/ORC-DEMO-004",
            "asking_price": Decimal("9200.00"),
            "currency": "SGD",
            "availability_status": ListingAvailabilityStatus.AWAITING_VERIFICATION,
            "available_from": date(2026, 12, 15),
            "lease_min_months": 24,
            "lease_max_months": 36,
            "listing_status": PropertyListingStatus.ACTIVE,
        },
        {
            "property_key": "bishan_loft_1806",
            "source_name": "Direct Agency Sheet",
            "agent_name": "Mary Lim",
            "source_listing_id": "BISHAN-SHEET-505",
            "source_url": "https://example-agency.sg/listings/BISHAN-SHEET-505",
            "asking_price": Decimal("4200.00"),
            "currency": "SGD",
            "availability_status": ListingAvailabilityStatus.CONDITIONAL,
            "available_from": date(2026, 12, 1),
            "lease_min_months": 12,
            "lease_max_months": 12,
            "listing_status": PropertyListingStatus.ACTIVE,
        },
    ]

    created_listings = []
    for l_data in listings_data:
        prop = props_map[l_data["property_key"]]
        src = sources_map[l_data["source_name"]]
        agt = agents_map[l_data["agent_name"]]

        existing = (
            db.query(PropertyListing)
            .filter(
                PropertyListing.source_id == src.id,
                PropertyListing.source_listing_id == l_data["source_listing_id"],
            )
            .first()
        )
        if not existing:
            listing = PropertyListing(
                property_id=prop.id,
                source_id=src.id,
                agent_id=agt.id,
                source_listing_id=l_data["source_listing_id"],
                source_url=l_data["source_url"],
                asking_price=l_data["asking_price"],
                currency=l_data["currency"],
                availability_status=l_data["availability_status"],
                available_from=l_data["available_from"],
                lease_min_months=l_data["lease_min_months"],
                lease_max_months=l_data["lease_max_months"],
                listing_status=l_data["listing_status"],
                last_verified_at=l_data.get("last_verified_at"),
            )
            db.add(listing)
            db.commit()
            db.refresh(listing)
            created_listings.append(listing)
        else:
            created_listings.append(existing)

    return {
        "sources_count": len(sources_map),
        "agents_count": len(agents_map),
        "properties_count": len(props_map),
        "listings_count": len(created_listings),
    }
