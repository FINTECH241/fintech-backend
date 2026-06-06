from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.auth import (
    RegisterRequest, OTPVerifyRequest, OTPResendRequest,
    LoginRequest, TokenResponse, RefreshRequest,
    ProfileUpdate, ProfileResponse, MessageResponse,
)
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["Authentification"])


def _ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


# ── US-1.1 ────────────────────────────────────────────────────────────────────

@router.post("/register", response_model=MessageResponse, status_code=201)
def register(payload: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    """
    Étape 1 : enregistrer le numéro, recueillir le consentement CNPDCP,
    envoyer l'OTP par SMS.
    """
    result = auth_service.register_send_otp(db, payload, _ip(request))
    return result


@router.post("/register/verify", response_model=MessageResponse)
def verify_registration(
    payload: OTPVerifyRequest, request: Request, db: Session = Depends(get_db)
):
    """Étape 2 : valider l'OTP → compte actif."""
    return auth_service.register_verify_otp(db, payload, _ip(request))


@router.post("/register/resend-otp", response_model=MessageResponse)
def resend_otp(
    payload: OTPResendRequest, request: Request, db: Session = Depends(get_db)
):
    """Renvoyer un OTP (limité à OTP_MAX_RESEND fois par fenêtre)."""
    return auth_service.resend_otp(db, payload.phone, _ip(request))


# ── US-1.2 ────────────────────────────────────────────────────────────────────

@router.post("/login/send-otp", response_model=MessageResponse)
def login_send_otp(
    payload: OTPResendRequest, request: Request, db: Session = Depends(get_db)
):
    """
    Envoyer un OTP de connexion au numéro enregistré.
    Identique à resend mais sémantiquement distinct (login vs inscription).
    """
    return auth_service.login_send_otp(db, payload.phone, _ip(request))


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    """Connexion : vérification OTP → JWT access + refresh."""
    return auth_service.login(db, payload, _ip(request))


@router.post("/token/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest, request: Request, db: Session = Depends(get_db)):
    """Rotation du refresh token → nouveaux tokens."""
    return auth_service.refresh_tokens(db, payload.refresh_token, _ip(request))


@router.post("/logout", response_model=MessageResponse)
def logout(
    payload: RefreshRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Déconnexion : révocation du refresh token."""
    return auth_service.logout(db, payload.refresh_token, current_user.id, _ip(request))


# ── US-1.3 ────────────────────────────────────────────────────────────────────

@router.get("/profile", response_model=ProfileResponse)
def get_profile(current_user: User = Depends(get_current_user)):
    """Consulter son profil."""
    return current_user


@router.patch("/profile", response_model=ProfileResponse)
def update_profile(
    payload: ProfileUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mettre à jour nom et date de naissance (avant validation KYC)."""
    return auth_service.update_profile(db, current_user.id, payload, _ip(request))