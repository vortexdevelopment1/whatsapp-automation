"""
Demo Property Source Adapter
Generates synthetic rental listing datasets for testing, validation, and demo seeding.
Covers:
- Exact duplicate listings (same source & listing id)
- Updated same listing (price / availability changes)
- Same physical property with two different agents
- Same building but different units (#10-01, #10-02, #12-01)
- Similar address with missing unit requiring manual review
- Multiple currencies (SGD, AED)
- Various availability statuses (AVAILABLE, UNAVAILABLE, UNKNOWN, AWAITING_VERIFICATION)
- Multiple furnishing variants ("Fully Furnished", "semi-furnished", "bare", "unfurnished")
- Multiple property types ("Condominium", "condo", "apartment", "HDB flat", "Landed")
- Invalid rows for error handling (invalid price, malformed dates)
"""

import io
import csv
from typing import List, Dict, Any

class DemoPropertySourceAdapter:
    SOURCE_NAME = "Demo Synthetic Feed"
    SOURCE_CODE = "DEMO_FEED"

    @classmethod
    def generate_synthetic_rows(cls, count: int = 100) -> List[Dict[str, Any]]:
        """
        Generates deterministic synthetic rows showcasing all edge cases and scenarios.
        """
        rows: List[Dict[str, Any]] = []

        # 1. Base Canonical Property: Marina Bay Suites #15-02 (Agent Alice)
        rows.append({
            "source_listing_id": "DEMO-001",
            "source_url": "https://demo.property.internal/listings/001",
            "property_name": "Marina Bay Suites Luxury 2BR",
            "building_name": "Marina Bay Suites",
            "address_line_1": "3 Central Boulevard",
            "address_line_2": "#15-02",
            "postal_code": "018965",
            "city": "Singapore",
            "state_region": "Singapore",
            "country": "Singapore",
            "property_type": "Condominium",
            "bedrooms": "2 bed",
            "bathrooms": "2",
            "size_sqft": "1050",
            "furnishing": "Fully Furnished",
            "asking_price": "S$ 6,500",
            "currency": "SGD",
            "available_from": "2026-11-01",
            "lease_min_months": "12 months",
            "lease_max_months": "24",
            "availability_status": "available",
            "listing_status": "ACTIVE",
            "agent_name": "Alice Tan",
            "agent_agency": "PropNex Realty",
            "agent_registration_number": "R012345A",
            "agent_phone": "+65 9123 4567",
            "agent_email": "alice.tan@propnex.com.sg",
            "source_last_updated_at": "2026-10-01T08:00:00Z"
        })

        # 2. Same Physical Property as #1 (#15-02 Marina Bay Suites), but Different Agent & Source ID (Bob)
        # Expected: Attaches to the SAME canonical property, creates separate listing
        rows.append({
            "source_listing_id": "DEMO-002",
            "source_url": "https://demo.property.internal/listings/002",
            "property_name": "Stunning High Floor Marina Bay Suites",
            "building_name": "Marina Bay Suites",
            "address_line_1": "3 Central Boulevard",
            "address_line_2": "#15-02",
            "postal_code": "018965",
            "city": "Singapore",
            "state_region": "Singapore",
            "country": "Singapore",
            "property_type": "condo",
            "bedrooms": "2BR",
            "bathrooms": "2",
            "size_sqft": "1050",
            "furnishing": "full furnished",
            "asking_price": "6700",
            "currency": "SGD",
            "available_from": "2026-11-01",
            "lease_min_months": "1 year",
            "lease_max_months": "24",
            "availability_status": "available",
            "listing_status": "ACTIVE",
            "agent_name": "Bob Lim",
            "agent_agency": "ERA Realty",
            "agent_registration_number": "R067890B",
            "agent_phone": "6598765432",
            "agent_email": "bob.lim@era.com.sg",
            "source_last_updated_at": "2026-10-02T10:00:00Z"
        })

        # 3. Same Building, DIFFERENT Unit (#15-03)
        # Expected: Creates a NEW canonical property
        rows.append({
            "source_listing_id": "DEMO-003",
            "source_url": "https://demo.property.internal/listings/003",
            "property_name": "Marina Bay Suites 3BR Corner Unit",
            "building_name": "Marina Bay Suites",
            "address_line_1": "3 Central Boulevard",
            "address_line_2": "#15-03",
            "postal_code": "018965",
            "city": "Singapore",
            "state_region": "Singapore",
            "country": "Singapore",
            "property_type": "CONDO",
            "bedrooms": "3",
            "bathrooms": "3",
            "size_sqft": "1580",
            "furnishing": "Partially Furnished",
            "asking_price": "9,200",
            "currency": "SGD",
            "available_from": "2026-12-01",
            "lease_min_months": "24",
            "lease_max_months": "24",
            "availability_status": "available",
            "listing_status": "ACTIVE",
            "agent_name": "Alice Tan",
            "agent_agency": "PropNex Realty",
            "agent_registration_number": "R012345A",
            "agent_phone": "+65 9123 4567",
            "agent_email": "alice.tan@propnex.com.sg",
            "source_last_updated_at": "2026-10-03T09:00:00Z"
        })

        # 4. Same Building & Bedrooms, MISSING Unit number
        # Expected: Matches candidate Marina Bay Suites, flags as NEEDS_REVIEW (Uncertain duplicate)
        rows.append({
            "source_listing_id": "DEMO-004",
            "source_url": "https://demo.property.internal/listings/004",
            "property_name": "Marina Bay Suites 2-Bedroom For Rent",
            "building_name": "Marina Bay Suites",
            "address_line_1": "3 Central Boulevard",
            "address_line_2": "",
            "postal_code": "018965",
            "city": "Singapore",
            "state_region": "Singapore",
            "country": "Singapore",
            "property_type": "Condominium",
            "bedrooms": "2",
            "bathrooms": "2",
            "size_sqft": "1050",
            "furnishing": "Furnished",
            "asking_price": "6600",
            "currency": "SGD",
            "available_from": "2026-11-15",
            "lease_min_months": "12",
            "lease_max_months": "12",
            "availability_status": "check with agent",
            "listing_status": "ACTIVE",
            "agent_name": "Charlie Goh",
            "agent_agency": "Huttons Asia",
            "agent_registration_number": "R055443C",
            "agent_phone": "+65 8123 9999",
            "agent_email": "charlie@huttons.com",
            "source_last_updated_at": "2026-10-04T11:00:00Z"
        })

        # 5. Exact Source Duplicate of DEMO-001 (Same source_listing_id) with Updated Price
        # Expected: DUPLICATE_LISTING, updates DEMO-001 price to 6800
        rows.append({
            "source_listing_id": "DEMO-001",
            "source_url": "https://demo.property.internal/listings/001",
            "property_name": "Marina Bay Suites Luxury 2BR (Price Revised)",
            "building_name": "Marina Bay Suites",
            "address_line_1": "3 Central Boulevard",
            "address_line_2": "#15-02",
            "postal_code": "018965",
            "city": "Singapore",
            "state_region": "Singapore",
            "country": "Singapore",
            "property_type": "Condominium",
            "bedrooms": "2",
            "bathrooms": "2",
            "size_sqft": "1050",
            "furnishing": "Fully Furnished",
            "asking_price": "6800",
            "currency": "SGD",
            "available_from": "2026-11-01",
            "lease_min_months": "12",
            "lease_max_months": "24",
            "availability_status": "available",
            "listing_status": "ACTIVE",
            "agent_name": "Alice Tan",
            "agent_agency": "PropNex Realty",
            "agent_registration_number": "R012345A",
            "agent_phone": "+65 9123 4567",
            "agent_email": "alice.tan@propnex.com.sg",
            "source_last_updated_at": "2026-10-05T14:30:00Z"
        })

        # 6. Unavailable / Rented Property
        rows.append({
            "source_listing_id": "DEMO-006",
            "source_url": "https://demo.property.internal/listings/006",
            "property_name": "D'Leedon 1BR Cozy Flat",
            "building_name": "D'Leedon",
            "address_line_1": "1 Leedon Heights",
            "address_line_2": "#08-11",
            "postal_code": "267939",
            "city": "Singapore",
            "state_region": "Singapore",
            "country": "Singapore",
            "property_type": "Apartment",
            "bedrooms": "1",
            "bathrooms": "1",
            "size_sqft": "620",
            "furnishing": "bare",
            "asking_price": "3400",
            "currency": "SGD",
            "available_from": "2026-10-15",
            "lease_min_months": "12",
            "lease_max_months": "12",
            "availability_status": "rented",
            "listing_status": "INACTIVE",
            "agent_name": "David Koh",
            "agent_agency": "OrangeTee & Tie",
            "agent_registration_number": "R099887D",
            "agent_phone": "+65 9234 5678",
            "agent_email": "david.koh@orangetee.com",
            "source_last_updated_at": "2026-10-04T12:00:00Z"
        })

        # 7. AED Currency Example (Dubai Marina)
        rows.append({
            "source_listing_id": "DEMO-007",
            "source_url": "https://demo.property.internal/listings/007",
            "property_name": "Marina Gate 1 Tower Sea View",
            "building_name": "Marina Gate 1",
            "address_line_1": "Al Reshaas Street",
            "address_line_2": "Apt 2204",
            "postal_code": "00000",
            "city": "Dubai",
            "state_region": "Dubai",
            "country": "United Arab Emirates",
            "property_type": "Apartment",
            "bedrooms": "2 BR",
            "bathrooms": "3",
            "size_sqft": "1250",
            "furnishing": "Fully Furnished",
            "asking_price": "140,000",
            "currency": "AED",
            "available_from": "2026-11-01",
            "lease_min_months": "12",
            "lease_max_months": "12",
            "availability_status": "available",
            "listing_status": "ACTIVE",
            "agent_name": "Tariq Mansoor",
            "agent_agency": "Betterhomes",
            "agent_registration_number": "BRN-44556",
            "agent_phone": "+971 50 123 4567",
            "agent_email": "tariq@betterhomes.ae",
            "source_last_updated_at": "2026-10-06T10:00:00Z"
        })

        # 8. HDB Flat Example
        rows.append({
            "source_listing_id": "DEMO-008",
            "source_url": "https://demo.property.internal/listings/008",
            "property_name": "Pinnacle @ Duxton 4-Room Flat",
            "building_name": "The Pinnacle @ Duxton",
            "address_line_1": "1 Cantonment Road",
            "address_line_2": "#28-09",
            "postal_code": "080001",
            "city": "Singapore",
            "state_region": "Singapore",
            "country": "Singapore",
            "property_type": "HDB flat",
            "bedrooms": "3",
            "bathrooms": "2",
            "size_sqft": "1000",
            "furnishing": "semi-furnished",
            "asking_price": "4,500",
            "currency": "SGD",
            "available_from": "2026-11-01",
            "lease_min_months": "12",
            "lease_max_months": "24",
            "availability_status": "available",
            "listing_status": "ACTIVE",
            "agent_name": "Evelyn Wong",
            "agent_agency": "PropNex Realty",
            "agent_registration_number": "R088776E",
            "agent_phone": "+65 9345 6789",
            "agent_email": "evelyn.wong@propnex.com.sg",
            "source_last_updated_at": "2026-10-06T11:00:00Z"
        })

        # 9. Invalid Row: Negative Price
        rows.append({
            "source_listing_id": "DEMO-009-ERR",
            "source_url": "https://demo.property.internal/listings/009",
            "property_name": "Invalid Price Listing",
            "building_name": "Orchard Residences",
            "address_line_1": "238 Orchard Boulevard",
            "address_line_2": "#20-01",
            "postal_code": "237973",
            "city": "Singapore",
            "state_region": "Singapore",
            "country": "Singapore",
            "property_type": "Condo",
            "bedrooms": "3",
            "bathrooms": "3",
            "size_sqft": "1800",
            "furnishing": "Furnished",
            "asking_price": "-500",
            "currency": "SGD",
            "available_from": "2026-11-01",
            "lease_min_months": "12",
            "lease_max_months": "24",
            "availability_status": "available",
            "listing_status": "ACTIVE",
            "agent_name": "Test Agent",
            "agent_agency": "Agency",
            "agent_registration_number": "R000001Z",
            "agent_phone": "+65 9000 0001",
            "agent_email": "agent@test.com",
            "source_last_updated_at": "2026-10-06T12:00:00Z"
        })

        # 10. Invalid Row: Malformed Date & Inverted Lease
        rows.append({
            "source_listing_id": "DEMO-010-ERR",
            "source_url": "https://demo.property.internal/listings/010",
            "property_name": "Malformed Date Listing",
            "building_name": "Cairnhill Nine",
            "address_line_1": "9 Cairnhill Circle",
            "address_line_2": "#10-05",
            "postal_code": "229814",
            "city": "Singapore",
            "state_region": "Singapore",
            "country": "Singapore",
            "property_type": "Condo",
            "bedrooms": "1",
            "bathrooms": "1",
            "size_sqft": "650",
            "furnishing": "Furnished",
            "asking_price": "4200",
            "currency": "SGD",
            "available_from": "not-a-valid-date",
            "lease_min_months": "24",
            "lease_max_months": "12",  # min > max error!
            "availability_status": "available",
            "listing_status": "ACTIVE",
            "agent_name": "Test Agent 2",
            "agent_agency": "Agency",
            "agent_registration_number": "R000002Z",
            "agent_phone": "+65 9000 0002",
            "agent_email": "agent2@test.com",
            "source_last_updated_at": "2026-10-06T12:00:00Z"
        })

        # Remaining rows (11 to `count`) to make a full 100-row realistic dataset
        complexes = [
            ("The Sail @ Marina Bay", "4 Marina Boulevard", "018986", "CONDO", 3500, 7500),
            ("Reflections at Keppel Bay", "8 Keppel Bay View", "098417", "CONDO", 4000, 8500),
            ("Commonwealth Towers", "230 Commonwealth Avenue", "149739", "CONDO", 3200, 5200),
            ("High Park Residences", "21 Fernvale Road", "797645", "CONDO", 2500, 4200),
            ("Tre Ver", "60 Potong Pasir Avenue 1", "358389", "CONDO", 3100, 5000),
            ("Seaside Residences", "10 Siglap Link", "448875", "CONDO", 3400, 6800),
            ("Tiong Bahru View", "9B Boon Tiong Road", "162009", "HDB", 3300, 4600),
            ("SkyTerrace @ Dawson", "88 Dawson Road", "142088", "HDB", 3600, 4800),
            ("Guoco Tower Residences", "Wallich Street", "078881", "APARTMENT", 7000, 15000),
        ]

        agent_pool = [
            ("Grace Chen", "PropNex Realty", "R011223G", "+65 9111 2233", "grace@propnex.com"),
            ("Henry Tan", "ERA Realty", "R022334H", "+65 9222 3344", "henry@era.com"),
            ("Iris Wong", "OrangeTee & Tie", "R033445I", "+65 9333 4455", "iris@orangetee.com"),
            ("Jason Lee", "Huttons Asia", "R044556J", "+65 9444 5566", "jason@huttons.com"),
            ("Karen Koh", "SRI", "R055667K", "+65 9555 6677", "karen@sri.sg"),
        ]

        curr_id = 11
        while len(rows) < count:
            comp_idx = (curr_id - 11) % len(complexes)
            name, addr, postal, ptype, min_p, max_p = complexes[comp_idx]
            agent = agent_pool[(curr_id - 11) % len(agent_pool)]

            floor = 5 + (curr_id % 30)
            stack = 1 + (curr_id % 12)
            unit_str = f"#{floor:02d}-{stack:02d}"

            beds = 1 + (curr_id % 4)
            baths = 1 if beds == 1 else 2
            sqft = 450 + (beds * 320)
            price = min_p + (beds * 800)

            rows.append({
                "source_listing_id": f"DEMO-{curr_id:03d}",
                "source_url": f"https://demo.property.internal/listings/{curr_id:03d}",
                "property_name": f"{name} {beds}BR Suite",
                "building_name": name,
                "address_line_1": addr,
                "address_line_2": unit_str,
                "postal_code": postal,
                "city": "Singapore",
                "state_region": "Singapore",
                "country": "Singapore",
                "property_type": ptype,
                "bedrooms": f"{beds}",
                "bathrooms": f"{baths}",
                "size_sqft": str(sqft),
                "furnishing": "Furnished" if curr_id % 2 == 0 else "Partially Furnished",
                "asking_price": f"S$ {price:,}",
                "currency": "SGD",
                "available_from": "2026-11-01",
                "lease_min_months": "12",
                "lease_max_months": "24",
                "availability_status": "AVAILABLE",
                "listing_status": "ACTIVE",
                "agent_name": agent[0],
                "agent_agency": agent[1],
                "agent_registration_number": agent[2],
                "agent_phone": agent[3],
                "agent_email": agent[4],
                "source_last_updated_at": "2026-10-07T00:00:00Z"
            })
            curr_id += 1

        return rows

    @classmethod
    def generate_csv_content(cls, count: int = 100) -> str:
        """
        Converts the synthetic rows into a valid CSV string.
        """
        rows = cls.generate_synthetic_rows(count)
        if not rows:
            return ""

        output = io.StringIO()
        fieldnames = list(rows[0].keys())
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)

        return output.getvalue()
