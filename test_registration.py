import re
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, EmailStr, ValidationError

class NepalTelecomOperator(str, Enum):
    ntc = "Nepal Telecom (NTC)"
    ncell = "Ncell"

class TenantRegistrationPayload(BaseModel):
    organization_name: str = Field(..., max_length=100)
    email_address: str
    phone_number: str
    telecom_carrier: NepalTelecomOperator
    is_sms_verified: bool = False

    def validate_phone(self):
        clean_number = re.sub(r'\s+', '', self.phone_number)
        nepal_phone_regex = r"^\+977(98|97)\d{8}$"
        if not re.match(nepal_phone_regex, clean_number):
            return False
        return True

if __name__ == "__main__":
    print("[Validation Engine] Testing registration entries...")
    
    # Test an invalid phone number configuration structure
    bad_entry = TenantRegistrationPayload(
        organization_name="Kathmandu Shop",
        email_address="shop@gmail.com",
        phone_number="98510-Wrong",
        telecom_carrier=NepalTelecomOperator.ntc
    )
    
    # Test a valid, structured Nepali mobile payload layout
    good_entry = TenantRegistrationPayload(
        organization_name="Lalitpur Tech Hub",
        email_address="tech@hub.np",
        phone_number="+9779851234567",
        telecom_carrier=NepalTelecomOperator.ncell
    )
    
    print(f" -> Testing Bad Phone Payload Result: {'Valid' if bad_entry.validate_phone() else 'Rejected'}")
    print(f" -> Testing Good Phone Payload Result: {'Valid' if good_entry.validate_phone() else 'Rejected'}")
