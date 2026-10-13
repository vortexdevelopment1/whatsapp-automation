import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple


PROPERTY_TYPE_MAP = {
    "condo": "CONDO",
    "condominium": "CONDO",
    "private condo": "CONDO",
    "apartment": "APARTMENT",
    "apt": "APARTMENT",
    "flat": "APARTMENT",
    "hdb": "HDB",
    "hdb flat": "HDB",
    "bto": "HDB",
    "landed": "LANDED",
    "terrace": "LANDED",
    "semi-d": "LANDED",
    "semi-detached": "LANDED",
    "bungalow": "LANDED",
    "good class bungalow": "LANDED",
    "room": "ROOM",
    "common room": "ROOM",
    "master room": "ROOM",
    "studio": "STUDIO",
    "other": "OTHER",
    "unknown": "UNKNOWN",
}

FURNISHING_MAP = {
    "furnished": "FURNISHED",
    "fully furnished": "FURNISHED",
    "full furnished": "FURNISHED",
    "partially furnished": "PARTIALLY_FURNISHED",
    "partially_furnished": "PARTIALLY_FURNISHED",
    "partial furnished": "PARTIALLY_FURNISHED",
    "semi furnished": "PARTIALLY_FURNISHED",
    "semi-furnished": "PARTIALLY_FURNISHED",
    "unfurnished": "UNFURNISHED",
    "bare": "UNFURNISHED",
    "empty": "UNFURNISHED",
    "flexible": "FLEXIBLE",
    "either": "FLEXIBLE",
    "either is okay": "FLEXIBLE",
    "any": "FLEXIBLE",
    "no preference": "FLEXIBLE",
    "unknown": "UNKNOWN",
}


def normalize_property_type(val: Any) -> Optional[str]:
    if not val:
        return None
    val_str = str(val).strip().lower()
    for pattern, canonical in PROPERTY_TYPE_MAP.items():
        if pattern in val_str:
            return canonical
    return "OTHER"


def normalize_furnishing(val: Any) -> Optional[str]:
    if not val:
        return None
    val_str = str(val).strip().lower()
    for pattern, canonical in FURNISHING_MAP.items():
        if pattern in val_str:
            return canonical
    return "UNKNOWN"


def normalize_lease_duration(val: Any) -> Optional[int]:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        int_val = int(val)
        return int_val if int_val > 0 else None

    val_str = str(val).strip().lower()
    if "two year" in val_str or "2 year" in val_str or "24 month" in val_str:
        return 24
    if "one year" in val_str or "1 year" in val_str or "12 month" in val_str or "yearly" in val_str:
        return 12
    if "six month" in val_str or "6 month" in val_str:
        return 6
    if "three month" in val_str or "3 month" in val_str:
        return 3

    m = re.search(r"\b(\d+)\s*(?:month|mth|m|year|yr)s?\b", val_str)
    if m:
        num = int(m.group(1))
        if "year" in val_str or "yr" in val_str:
            return num * 12
        return num if num > 0 else None

    return None


def normalize_occupants(val: Any) -> Optional[int]:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        int_val = int(val)
        return int_val if int_val > 0 else None

    val_str = str(val).strip().lower()
    if val_str in ("just me", "alone", "myself", "1 pax", "single", "one person"):
        return 1
    if any(k in val_str for k in ("me and my wife", "me and my husband", "me and my partner", "couple", "2 pax", "two person", "2 people")):
        return 2
    if "family of four" in val_str or "family of 4" in val_str or "4 pax" in val_str:
        return 4
    if "family of three" in val_str or "family of 3" in val_str or "3 pax" in val_str:
        return 3

    m = re.search(r"\b(\d+)\s*(?:pax|people|person|occupant|tenant)s?\b", val_str)
    if m:
        num = int(m.group(1))
        return num if num > 0 else None

    return None


def normalize_budget(val: Any) -> Optional[float]:
    if val is None:
        return None
    if isinstance(val, (int, float, Decimal)):
        f_val = float(val)
        return round(f_val, 2) if f_val >= 0 else None

    val_str = str(val).strip().lower().replace(",", "")
    # Check for 'k' notation e.g. 3.5k -> 3500
    m_k = re.search(r"(\d+(?:\.\d+)?)\s*k\b", val_str)
    if m_k:
        return round(float(m_k.group(1)) * 1000, 2)

    m = re.search(r"(\d+(?:\.\d+)?)", val_str)
    if m:
        f_val = float(m.group(1))
        return round(f_val, 2) if f_val >= 0 else None

    return None


def normalize_move_in_date(val: Any, reference_date: Optional[date] = None) -> Tuple[Optional[str], bool]:
    """
    Returns (normalized_iso_date_str, is_ambiguous).
    If unambiguous date string is parsed, is_ambiguous=False.
    If approximate or relative (e.g. 'next month', 'end of year'), is_ambiguous=True.
    """
    if val is None:
        return None, False

    ref = reference_date or date.today()

    val_str = str(val).strip().lower()

    # Direct ISO format YYYY-MM-DD
    iso_match = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", val_str)
    if iso_match:
        return iso_match.group(0), False

    # Standard date expressions e.g. '1 december 2026' or 'december 1 2026'
    months = {
        "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3,
        "april": 4, "apr": 4, "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7,
        "august": 8, "aug": 8, "september": 9, "sep": 9, "sept": 9,
        "october": 10, "oct": 10, "november": 11, "nov": 11, "december": 12, "dec": 12
    }

    # Match '1 december' or '1 dec 2026'
    m_d = re.search(r"(\d{1,2})(?:st|nd|rd|th)?\s+([a-z]+)(?:\s+(\d{4}))?", val_str)
    if m_d and m_d.group(2) in months:
        day = int(m_d.group(1))
        month = months[m_d.group(2)]
        year = int(m_d.group(3)) if m_d.group(3) else ref.year
        try:
            parsed = date(year, month, day)
            # If date in the past for current year and no year specified, assume next year
            if not m_d.group(3) and parsed < ref:
                parsed = date(year + 1, month, day)
            return parsed.isoformat(), False
        except ValueError:
            pass

    # Relative expressions
    if "next month" in val_str:
        next_month = ref.month + 1
        year = ref.year
        if next_month > 12:
            next_month = 1
            year += 1
        # Default to 1st of next month, but mark ambiguous
        return date(year, next_month, 1).isoformat(), True

    if "end of the year" in val_str or "end of year" in val_str:
        return date(ref.year, 12, 1).isoformat(), True

    return None, True


def normalize_locations(val: Any) -> List[str]:
    if not val:
        return []
    if isinstance(val, list):
        cleaned = [str(loc).strip() for loc in val if str(loc).strip()]
        return cleaned
    if isinstance(val, str):
        # Split on commas, 'or', 'and', '/'
        parts = re.split(r",|\bor\b|\band\b|/", val, flags=re.IGNORECASE)
        cleaned = [p.strip() for p in parts if p.strip()]
        return cleaned
    return []
