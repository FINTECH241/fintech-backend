"""
Service d'authentification — Sprint 1
Couvre US-1.1, US-1.2, US-1.3
"""
import hashlib
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token, create_refresh_token, decode_token
from app.models.user import User
from app.models.token import RefreshToken
from app.schemas.auth import (
    RegisterRequest, OTPVerifyRequest, LoginRequest,
    ProfileUpdate, TokenResponse,
)
from app.services.otp_service import generate_and_store_otp, verify_otp, send_otp_sms


# ── Utilitaire ────────────────────────────────────────────────────────────────

def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


# ── US-1.1 : Inscription ──────────────────────────────────────────────────────

def register_send_otp(db: Session, payload: RegisterRequest, ip: str) -> dict:
    """Étape 1/2 : enregistrer le consentement et envoyer l'OTP."""
    from app.core.audit import log_event

    user = db.query(User).filter(User.phone == payload.phone).first()
    if user and user.is_phone_verified:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ce numéro est déjà enregistré.",
        )

    if not user:
        user = User(
            phone=payload.phone,
            consent_given=payload.consent,
            consent_at=datetime.now(timezone.utc),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        user.consent_given = payload.consent
        user.consent_at = datetime.now(timezone.utc)
        db.commit()

    try:
        otp = generate_and_store_otp(payload.phone)
        send_otp_sms(payload.phone, otp)
    except ValueError as e:
        log_event(db, "REGISTER_OTP_SENT", user_id=user.id, phone=payload.phone,
                  ip=ip, success=False, details={"reason": str(e)})
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(e))

    log_event(db, "REGISTER_OTP_SENT", user_id=user.id, phone=payload.phone, ip=ip)
    return {"message": "OTP envoyé. Valable 5 minutes."}


def register_verify_otp(db: Session, payload: OTPVerifyRequest, ip: str) -> dict:
    """Étape 2/2 : vérifier l'OTP et activer le compte."""
    from app.core.audit import log_event

    user = db.query(User).filter(User.phone == payload.phone).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable.")

    if not verify_otp(payload.phone, payload.otp):
        log_event(db, "REGISTER_OTP_VERIFIED", user_id=user.id, phone=payload.phone,
                  ip=ip, success=False, details={"reason": "OTP invalide ou expiré"})
        raise HTTPException(status_code=400, detail="OTP invalide ou expiré.")

    user.is_phone_verified = True
    db.commit()
    log_event(db, "REGISTER_OTP_VERIFIED", user_id=user.id, phone=payload.phone, ip=ip)
    return {"message": "Numéro vérifié. Compte actif."}


def resend_otp(db: Session, phone: str, ip: str) -> dict:
    """Renvoi OTP pendant l'inscription (numéros non encore vérifiés)."""
    from app.core.audit import log_event
    user = db.query(User).filter(User.phone == phone).first()
    if not user:
        raise HTTPException(status_code=404, detail="Numéro non trouvé.")
    if user.is_phone_verified:
        raise HTTPException(status_code=409, detail="Numéro déjà vérifié.")

    try:
        otp = generate_and_store_otp(phone)
        send_otp_sms(phone, otp)
    except ValueError as e:
        log_event(db, "REGISTER_OTP_SENT", user_id=user.id, phone=phone,
                  ip=ip, success=False, details={"reason": str(e)})
        raise HTTPException(status_code=429, detail=str(e))

    log_event(db, "REGISTER_OTP_SENT", user_id=user.id, phone=phone, ip=ip,
              details={"action": "resend"})
    return {"message": "OTP renvoyé."}


def login_send_otp(db: Session, phone: str, ip: str) -> dict:
    """Envoie un OTP pour la connexion — numéros vérifiés uniquement."""
    from app.core.audit import log_event
    user = db.query(User).filter(User.phone == phone).first()
    if not user or not user.is_phone_verified:
        raise HTTPException(status_code=404, detail="Numéro non trouvé ou non vérifié.")

    try:
        otp = generate_and_store_otp(phone)
        send_otp_sms(phone, otp)
    except ValueError as e:
        log_event(db, "LOGIN_OTP_SENT", user_id=user.id, phone=phone,
                  ip=ip, success=False, details={"reason": str(e)})
        raise HTTPException(status_code=429, detail=str(e))

    log_event(db, "LOGIN_OTP_SENT", user_id=user.id, phone=phone, ip=ip)
    return {"message": "OTP envoyé. Valable 5 minutes."}


# ── US-1.2 : Login ────────────────────────────────────────────────────────────

def login(db: Session, payload: LoginRequest, ip: str) -> TokenResponse:
    from app.core.audit import log_event

    user = db.query(User).filter(User.phone == payload.phone).first()
    if not user or not user.is_phone_verified:
        raise HTTPException(status_code=401, detail="Identifiants invalides.")

    now = datetime.now(timezone.utc)
    now_naive = now.replace(tzinfo=None)

    def _as_naive(dt):
        return dt.replace(tzinfo=None) if dt.tzinfo else dt

    if user.locked_until and _as_naive(user.locked_until) > now_naive:
        remaining = int((_as_naive(user.locked_until) - now_naive).total_seconds() / 60) + 1
        log_event(db, "LOGIN_LOCKED", user_id=user.id, phone=payload.phone, ip=ip,
                  success=False, details={"locked_until": user.locked_until.isoformat()})
        raise HTTPException(
            status_code=423,
            detail=f"Compte verrouillé. Réessayez dans {remaining} minute(s).",
        )

    if not verify_otp(payload.phone, payload.otp):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= settings.MAX_LOGIN_ATTEMPTS:
            user.locked_until = now + timedelta(minutes=settings.LOGIN_LOCKOUT_MINUTES)
            db.commit()
            log_event(db, "LOGIN_LOCKED", user_id=user.id, phone=payload.phone, ip=ip,
                      success=False, details={"attempts": user.failed_login_attempts})
            raise HTTPException(status_code=423, detail="Compte verrouillé temporairement.")
        db.commit()
        log_event(db, "LOGIN_FAILED", user_id=user.id, phone=payload.phone, ip=ip,
                  success=False, details={"attempts": user.failed_login_attempts})
        raise HTTPException(status_code=401, detail="OTP invalide.")

    user.failed_login_attempts = 0
    user.locked_until = None
    db.commit()

    access = create_access_token(str(user.id))
    refresh = create_refresh_token(str(user.id))

    rt = RefreshToken(
        user_id=user.id,
        token_hash=_hash_token(refresh),
        expires_at=now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    db.add(rt)
    db.commit()

    log_event(db, "LOGIN_SUCCESS", user_id=user.id, phone=payload.phone, ip=ip)
    return TokenResponse(access_token=access, refresh_token=refresh)


def refresh_tokens(db: Session, refresh_token: str, ip: str) -> TokenResponse:
    from app.core.audit import log_event
    from jose import JWTError

    try:
        payload = decode_token(refresh_token)
    except JWTError:
        raise HTTPException(status_code=401, detail="Refresh token invalide.")

    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Token de mauvais type.")

    token_hash = _hash_token(refresh_token)
    stored = db.query(RefreshToken).filter(
        RefreshToken.token_hash == token_hash,
        RefreshToken.is_revoked == False,
    ).first()

    if not stored:
        raise HTTPException(status_code=401, detail="Token révoqué ou inconnu.")

    stored.is_revoked = True
    db.commit()

    user_id = payload["sub"]
    new_access = create_access_token(user_id)
    new_refresh = create_refresh_token(user_id)

    now = datetime.now(timezone.utc)
    db.add(RefreshToken(
        user_id=int(user_id),
        token_hash=_hash_token(new_refresh),
        expires_at=now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    ))
    db.commit()

    log_event(db, "TOKEN_REFRESH", user_id=int(user_id), ip=ip)
    return TokenResponse(access_token=new_access, refresh_token=new_refresh)


def logout(db: Session, refresh_token: str, user_id: int, ip: str) -> dict:
    from app.core.audit import log_event

    token_hash = _hash_token(refresh_token)
    stored = db.query(RefreshToken).filter(
        RefreshToken.token_hash == token_hash,
        RefreshToken.user_id == user_id,
    ).first()

    if stored:
        stored.is_revoked = True
        db.commit()

    log_event(db, "TOKEN_REVOKE", user_id=user_id, ip=ip)
    return {"message": "Déconnecté avec succès."}


# ── US-1.3 : Profil ───────────────────────────────────────────────────────────

def update_profile(db: Session, user_id: int, payload: ProfileUpdate, ip: str) -> User:
    from app.core.audit import log_event

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable.")

    if user.kyc_status == "validated":
        raise HTTPException(
            status_code=403,
            detail="Profil verrouillé après validation KYC.",
        )

    changed = {}
    if payload.full_name is not None:
        user.full_name = payload.full_name
        changed["full_name"] = True
    if payload.date_of_birth is not None:
        user.date_of_birth = payload.date_of_birth
        changed["date_of_birth"] = True

    db.commit()
    db.refresh(user)
    log_event(db, "PROFILE_UPDATED", user_id=user.id, ip=ip, details={"fields": list(changed.keys())})
    return user