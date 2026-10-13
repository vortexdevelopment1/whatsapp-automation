from typing import Optional
import phonenumbers
from phonenumbers import PhoneNumberFormat, NumberParseException


class PhoneNormalizationError(ValueError):
    """Raised when phone number parsing or validation fails."""
    pass


def normalize_phone_number(phone: str, default_region: str = "SG") -> str:
    """
    Normalizes a phone number to standard E.164 format (e.g. +6591234567).
    
    Supports:
    - '+65 9123 4567' -> '+6591234567'
    - '6591234567' -> '+6591234567'
    - '+6591234567' -> '+6591234567'
    - '91234567' (default SG) -> '+6591234567'
    - '+1 650 253 0000' -> '+16502530000'
    
    Raises:
    - PhoneNormalizationError: If phone is empty, malformed, or ambiguous.
    """
    if not phone or not phone.strip():
        raise PhoneNormalizationError("Phone number cannot be empty.")

    clean_phone = phone.strip()

    # If starts with digits e.g. 6591234567 (Singapore country code without +)
    if not clean_phone.startswith("+"):
        if clean_phone.startswith("65") and len(clean_phone) >= 10:
            candidate = "+" + clean_phone
            try:
                parsed = phonenumbers.parse(candidate, None)
                if phonenumbers.is_valid_number(parsed):
                    return phonenumbers.format_number(parsed, PhoneNumberFormat.E164)
            except NumberParseException:
                pass

        try:
            parsed = phonenumbers.parse(clean_phone, default_region)
            if not phonenumbers.is_valid_number(parsed):
                raise PhoneNormalizationError(f"Invalid phone number format: '{phone}'")
            return phonenumbers.format_number(parsed, PhoneNumberFormat.E164)
        except NumberParseException as e:
            raise PhoneNormalizationError(f"Failed to parse phone number '{phone}': {str(e)}")

    # Starts with +: Parse as full international number
    try:
        parsed = phonenumbers.parse(clean_phone, None)
        if not phonenumbers.is_valid_number(parsed):
            raise PhoneNormalizationError(f"Invalid international phone number: '{phone}'")
        return phonenumbers.format_number(parsed, PhoneNumberFormat.E164)
    except NumberParseException as e:
        raise PhoneNormalizationError(f"Failed to parse international phone number '{phone}': {str(e)}")
