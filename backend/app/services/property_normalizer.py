import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Optional, Tuple

from app.models.enums import (
    PropertyType,
    FurnishingType,
    ListingAvailabilityStatus,
)
from app.services.phone_service import normalize_phone_number, PhoneNormalizationError


ROAD_ABBREVIATIONS = {
    r"\brd\.?\b": "road",
    r"\bst\.?\b": "street",
    r"\bave\.?\b": "avenue",
    r"\bav\.?\b": "avenue",
    r"\bdr\.?\b": "drive",
    r"\bcres\.?\b": "crescent",
    r"\bcl\.?\b": "close",
    r"\bblvd\.?\b": "boulevard",
    r"\bpl\.?\b": "place",
    r"\bter\.?\b": "terrace",
    r"\bctrl\.?\b": "central",
    r"\bcntr\.?\b": "central",
    r"\bsq\.?\b": "square",
    r"\bln\.?\b": "lane",
    r"\bhwy\.?\b": "highway",
    r"\bnth\.?\b": "north",
    r"\bsth\.?\b": "south",
}


class PropertyNormalizer:
    @staticmethod
    def normalize_unit_number(val: Optional[str]) -> Optional[str]:
        if not val or not str(val).strip():
            return None
        cleaned = str(val).strip().upper()
        # Remove prefix '#' if present for parsing
        without_hash = cleaned.lstrip("#").strip()
        # Look for floor-stack format e.g. 08-04, 8-4, 8/4
        m = re.match(r"^(\d{1,3})[\-\/](\d{1,4}[A-Z]?)$", without_hash)
        if m:
            floor = m.group(1).zfill(2)
            stack = m.group(2)
            # If stack is pure digits, pad to 2 digits
            if stack.isdigit():
                stack = stack.zfill(2)
            return f"#{floor}-{stack}"
        # If it doesn't match standard floor-stack, ensure leading '#'
        if not cleaned.startswith("#"):
            return f"#{cleaned}"
        return cleaned

    @classmethod
    def normalize_address(
        cls,
        address_line_1: Optional[str],
        address_line_2: Optional[str] = None,
        unit_number: Optional[str] = None,
        building_name: Optional[str] = None,
        postal_code: Optional[str] = None,
        city: Optional[str] = "Singapore",
        country: Optional[str] = "Singapore",
    ) -> Dict[str, Optional[str]]:
        # If unit_number is not explicitly given, try extracting from address_line_2 or address_line_1
        if not unit_number and address_line_2:
            m_unit = re.search(r"#?\d{1,3}[\-\/]\d{1,4}[A-Za-z]?", address_line_2)
            if m_unit:
                unit_number = m_unit.group(0)
            elif address_line_2.strip().startswith("#"):
                unit_number = address_line_2.strip()
        if not unit_number and address_line_1:
            m_unit = re.search(r"#\d{1,3}[\-\/]\d{1,4}[A-Za-z]?", address_line_1)
            if m_unit:
                unit_number = m_unit.group(0)

        norm_unit = cls.normalize_unit_number(unit_number)

        # Normalize address line 1
        norm_addr = ""
        if address_line_1:
            raw = address_line_1.strip().lower()
            # Replace common road abbreviations
            for pattern, replacement in ROAD_ABBREVIATIONS.items():
                raw = re.sub(pattern, replacement, raw)
            # Remove redundant commas and multiple spaces
            raw = re.sub(r"[,\.]+", " ", raw)
            norm_addr = re.sub(r"\s+", " ", raw).strip()

        # Clean postal code (6 digits in SG)
        norm_postal = None
        if postal_code:
            digits = re.sub(r"\D", "", str(postal_code).strip())
            if digits:
                norm_postal = digits.zfill(6) if len(digits) <= 6 else digits

        norm_building = ""
        if building_name:
            norm_building = re.sub(r"\s+", " ", building_name.strip().lower())

        norm_country = (country or "Singapore").strip().lower()

        # Build address fingerprint
        fingerprint_parts = [norm_country]
        if norm_postal:
            fingerprint_parts.append(norm_postal)
        elif norm_building:
            fingerprint_parts.append(norm_building)
        elif norm_addr:
            fingerprint_parts.append(norm_addr)

        if norm_unit:
            fingerprint_parts.append(norm_unit.lower())

        fingerprint = ":".join(fingerprint_parts) if len(fingerprint_parts) > 1 else None

        return {
            "address_normalized": norm_addr or None,
            "unit_normalized": norm_unit,
            "postal_code_normalized": norm_postal,
            "building_normalized": norm_building or None,
            "property_fingerprint": fingerprint,
        }

    @staticmethod
    def normalize_property_type(val: Any) -> PropertyType:
        if not val:
            return PropertyType.OTHER
        val_str = str(val).strip().lower()
        if any(k in val_str for k in ("hdb", "bto", "executive flat")):
            return PropertyType.HDB
        if any(k in val_str for k in ("condo", "condominium")):
            return PropertyType.CONDO
        if any(k in val_str for k in ("apartment", "apt", "flat")):
            return PropertyType.APARTMENT
        if any(k in val_str for k in ("landed", "terrace", "semi-d", "bungalow", "good class")):
            return PropertyType.LANDED
        if "studio" in val_str:
            return PropertyType.STUDIO
        if "room" in val_str:
            return PropertyType.ROOM
        if any(k in val_str for k in ("commercial", "office", "shophouse")):
            return PropertyType.COMMERCIAL
        return PropertyType.OTHER

    @staticmethod
    def normalize_furnishing(val: Any) -> FurnishingType:
        if not val:
            return FurnishingType.UNKNOWN
        val_str = str(val).strip().lower()
        if any(k in val_str for k in ("fully", "full", "furnished")) and "unfurnished" not in val_str and "partially" not in val_str and "semi" not in val_str:
            return FurnishingType.FURNISHED
        if any(k in val_str for k in ("partially", "partial", "semi")):
            return FurnishingType.PARTIALLY_FURNISHED
        if any(k in val_str for k in ("unfurnished", "bare", "empty")):
            return FurnishingType.UNFURNISHED
        if any(k in val_str for k in ("flexible", "either", "no preference", "negotiable")):
            return FurnishingType.FLEXIBLE
        return FurnishingType.UNKNOWN

    @staticmethod
    def normalize_currency(val: Any, default_currency: str = "SGD", **kwargs) -> Tuple[str, bool]:
        fallback = kwargs.get("default", default_currency)
        if not val or not str(val).strip():
            return fallback.upper(), True
        val_str = str(val).strip().upper()
        if any(k in val_str for k in ("S$", "SGD", "SINGAPORE DOLLAR", "SG$")):
            return "SGD", False
        if any(k in val_str for k in ("AED", "DHS", "DIRHAM")):
            return "AED", False
        if any(k in val_str for k in ("USD", "US$", "DOLLAR")):
            return "USD", False
        if any(k in val_str for k in ("EUR", "€", "EURO")):
            return "EUR", False
        if any(k in val_str for k in ("GBP", "£", "POUND")):
            return "GBP", False
        cleaned = re.sub(r"[^A-Z]", "", val_str)
        if len(cleaned) == 3:
            return cleaned, False
        return fallback.upper(), True

    @staticmethod
    def normalize_price(val: Any) -> Optional[Decimal]:
        if val is None or str(val).strip() == "":
            return None
        if isinstance(val, (int, float, Decimal)):
            d = Decimal(str(val))
            if d < 0:
                raise ValueError("Asking price cannot be negative.")
            return d.quantize(Decimal("0.01"))
        val_str = str(val).strip()
        is_negative = val_str.startswith("-") or "-" in val_str
        # Remove currency symbols and common words e.g. "SGD 3,500/mo" -> "3500"
        cleaned = re.sub(r"[^\d\.]", "", val_str.replace(",", ""))
        if not cleaned:
            raise ValueError(f"Unable to parse numeric price from '{val}'.")
        if is_negative:
            raise ValueError("Asking price cannot be negative.")
        try:
            d = Decimal(cleaned)
            if d < 0:
                raise ValueError("Asking price cannot be negative.")
            return d.quantize(Decimal("0.01"))
        except InvalidOperation:
            raise ValueError(f"Invalid price value '{val}'.")

    @staticmethod
    def normalize_bedrooms(val: Any) -> Optional[int]:
        if val is None or str(val).strip() == "":
            return None
        val_str = str(val).strip().lower()
        if "studio" in val_str:
            return 0
        m = re.search(r"\b(\d+)\s*(?:bed|br|bedroom|rooms?)?\b", val_str)
        if m:
            num = int(m.group(1))
            if num < 0:
                raise ValueError("Bedrooms cannot be negative.")
            return num
        return None

    @staticmethod
    def normalize_bathrooms(val: Any) -> Optional[Decimal]:
        if val is None or str(val).strip() == "":
            return None
        val_str = str(val).strip().lower()
        m = re.search(r"(\d+(?:\.\d+)?)\s*(?:bath|ba|bathroom)?", val_str)
        if m:
            num = Decimal(m.group(1))
            if num < 0:
                raise ValueError("Bathrooms cannot be negative.")
            return num.quantize(Decimal("0.1"))
        return None

    @staticmethod
    def normalize_lease_terms(min_val: Any, max_val: Any) -> Tuple[Optional[int], Optional[int]]:
        def parse_months(v: Any) -> Optional[int]:
            if v is None or str(v).strip() == "":
                return None
            val_s = str(v).strip().lower()
            if "two year" in val_s or "2 year" in val_s or "24 month" in val_s:
                return 24
            if "one year" in val_s or "1 year" in val_s or "12 month" in val_s or "yearly" in val_s:
                return 12
            if "six month" in val_s or "6 month" in val_s:
                return 6
            m = re.search(r"\b(\d+)\s*(?:month|mth|m|year|yr)?s?\b", val_s)
            if m:
                num = int(m.group(1))
                if "year" in val_s or "yr" in val_s:
                    return num * 12
                return num
            return None

        min_m = parse_months(min_val)
        max_m = parse_months(max_val)

        if min_m is not None and min_m <= 0:
            raise ValueError("Minimum lease duration must be greater than 0.")
        if max_m is not None and max_m <= 0:
            raise ValueError("Maximum lease duration must be greater than 0.")
        if min_m is not None and max_m is not None and min_m > max_m:
            raise ValueError("Minimum lease duration cannot exceed maximum lease duration.")

        return min_m, max_m

    @staticmethod
    def normalize_date(val: Any) -> Optional[date]:
        if val is None or str(val).strip() == "":
            return None
        if isinstance(val, date):
            return val
        if isinstance(val, datetime):
            return val.date()

        val_str = str(val).strip()
        # ISO format YYYY-MM-DD
        m_iso = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})", val_str)
        if m_iso:
            return date(int(m_iso.group(1)), int(m_iso.group(2)), int(m_iso.group(3)))

        # DD/MM/YYYY or DD-MM-YYYY
        m_slash = re.match(r"^(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{4})$", val_str)
        if m_slash:
            return date(int(m_slash.group(3)), int(m_slash.group(2)), int(m_slash.group(1)))

        # Month names e.g. 1 Dec 2026, Dec 1 2026
        months = {
            "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
            "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
            "aug": 8, "august": 8, "sep": 9, "september": 9, "oct": 10, "october": 10,
            "nov": 11, "november": 11, "dec": 12, "december": 12,
        }
        m_name = re.search(r"(\d{1,2})(?:st|nd|rd|th)?\s+([a-zA-Z]+)\s+(\d{4})", val_str)
        if m_name and m_name.group(2).lower() in months:
            return date(int(m_name.group(3)), months[m_name.group(2).lower()], int(m_name.group(1)))

        raise ValueError(f"Unrecognized date format: '{val}'.")

    @staticmethod
    def normalize_availability(val: Any) -> ListingAvailabilityStatus:
        if not val or not str(val).strip():
            return ListingAvailabilityStatus.UNKNOWN
        val_str = str(val).strip().lower()
        if any(k in val_str for k in ("available", "vacant", "immediate")):
            return ListingAvailabilityStatus.AVAILABLE
        if any(k in val_str for k in ("taken", "rented", "not available", "leased", "unavailable")):
            return ListingAvailabilityStatus.UNAVAILABLE
        if any(k in val_str for k in ("check with agent", "verifying", "pending", "awaiting")):
            return ListingAvailabilityStatus.AWAITING_VERIFICATION
        if any(k in val_str for k in ("conditional", "subject to")):
            return ListingAvailabilityStatus.CONDITIONAL
        return ListingAvailabilityStatus.UNKNOWN

    @staticmethod
    def normalize_agent(
        name: Optional[str],
        phone: Optional[str] = None,
        email: Optional[str] = None,
        agency: Optional[str] = None,
        reg_no: Optional[str] = None,
    ) -> Dict[str, Optional[str]]:
        phone_norm = None
        if phone and str(phone).strip():
            try:
                phone_norm = normalize_phone_number(str(phone).strip())
            except PhoneNormalizationError:
                phone_norm = None

        email_clean = email.strip().lower() if email and str(email).strip() else None
        agency_clean = agency.strip() if agency and str(agency).strip() else None
        reg_clean = reg_no.strip().upper() if reg_no and str(reg_no).strip() else None
        name_clean = name.strip() if name and str(name).strip() else None

        return {
            "full_name": name_clean,
            "phone": phone.strip() if phone else None,
            "phone_normalized": phone_norm,
            "email": email_clean,
            "agency_name": agency_clean,
            "registration_number": reg_clean,
        }
