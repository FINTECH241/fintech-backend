from pydantic import BaseModel, field_validator
import re


# ── Helpers ──────────────────────────────────────────────────────────────────

PHONE_RE = re.compile(r"^\+?[1-9]\d{7,14}$")


def _validate_phone(v: str) -> str:
    v = v.strip().replace(" ", "")
    if not PHONE_RE.match(v):
        raise ValueError("Numéro de téléphone invalide (format international attendu).")
    return v


# ── US-1.1 : Inscription ──────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    phone: str
    consent: bool  # consentement CNPDCP obligatoire

    @field_validator("phone")
    @classmethod
    def phone_valid(cls, v):
        return _validate_phone(v)

    @field_validator("consent")
    @classmethod
    def consent_required(cls, v):
        if not v:
            raise ValueError("Le consentement CNPDCP est obligatoire.")
        return v


class OTPVerifyRequest(BaseModel):
    phone: str
    otp: str

    @field_validator("phone")
    @classmethod
    def phone_valid(cls, v):
        return _validate_phone(v)

    @field_validator("otp")
    @classmethod
    def otp_format(cls, v):
        if not re.fullmatch(r"\d{6}", v.strip()):
            raise ValueError("L'OTP doit être un code à 6 chiffres.")
        return v.strip()


class OTPResendRequest(BaseModel):
    phone: str

    @field_validator("phone")
    @classmethod
    def phone_valid(cls, v):
        return _validate_phone(v)


# ── US-1.2 : Connexion ────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    phone: str
    otp: str          # en contexte Mobile Money : login via OTP (pas de mot de passe)

    @field_validator("phone")
    @classmethod
    def phone_valid(cls, v):
        return _validate_phone(v)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


# ── US-1.3 : Profil ───────────────────────────────────────────────────────────

class ProfileUpdate(BaseModel):
    full_name: str | None = None
    date_of_birth: str | None = None   # YYYY-MM-DD

    @field_validator("full_name")
    @classmethod
    def name_not_empty(cls, v):
        if v is not None and len(v.strip()) < 2:
            raise ValueError("Le nom doit contenir au moins 2 caractères.")
        return v.strip() if v else v

    @field_validator("date_of_birth")
    @classmethod
    def dob_format(cls, v):
        if v is None:
            return v
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
            raise ValueError("Format date attendu : YYYY-MM-DD")
        return v


class ProfileResponse(BaseModel):
    id: int
    phone: str
    full_name: str | None
    date_of_birth: str | None
    is_phone_verified: bool
    kyc_status: str
    consent_given: bool

    class Config:
        from_attributes = True


# ── Réponses génériques ───────────────────────────────────────────────────────

class MessageResponse(BaseModel):
    message: str
    detail: str | None = None
