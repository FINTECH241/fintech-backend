"""
Service OTP — US-1.1
Règles :
  • OTP 6 chiffres, expire en 5 min (OTP_EXPIRE_MINUTES)
  • Invalidé après 1 usage réussi
  • Max OTP_MAX_RESEND renvois par OTP_RESEND_WINDOW_MINUTES (anti-abus)
  • Stockage Redis (clés préfixées "otp:" et "otp_count:")
"""
import random
import hashlib
from datetime import timedelta
from app.core.config import settings

# Import Redis — lazy pour faciliter les tests
def _get_redis():
    import redis
    return redis.from_url(settings.REDIS_URL, decode_responses=True)


def _otp_key(phone: str) -> str:
    return f"otp:{phone}"


def _count_key(phone: str) -> str:
    return f"otp_count:{phone}"


def _hash_otp(otp: str) -> str:
    """Ne stocke pas l'OTP en clair dans Redis."""
    return hashlib.sha256(otp.encode()).hexdigest()


def generate_and_store_otp(phone: str) -> str:
    """
    Génère un OTP, vérifie la limite de renvois, le stocke haché dans Redis.
    Lève ValueError si la limite de renvois est atteinte.
    Retourne l'OTP en clair (à envoyer par SMS).
    """
    r = _get_redis()
    count_key = _count_key(phone)
    current_count = int(r.get(count_key) or 0)

    if current_count >= settings.OTP_MAX_RESEND:
        raise ValueError(
            f"Limite de renvois atteinte. Réessayez dans "
            f"{settings.OTP_RESEND_WINDOW_MINUTES} minutes."
        )

    otp = f"{random.SystemRandom().randint(0, 999999):06d}"
    expire_sec = settings.OTP_EXPIRE_MINUTES * 60
    window_sec = settings.OTP_RESEND_WINDOW_MINUTES * 60

    # Stocker le hash de l'OTP
    r.setex(_otp_key(phone), expire_sec, _hash_otp(otp))

    # Incrémenter le compteur de renvois
    pipe = r.pipeline()
    pipe.incr(count_key)
    pipe.expire(count_key, window_sec)
    pipe.execute()

    return otp


def verify_otp(phone: str, otp: str) -> bool:
    """
    Vérifie l'OTP. Si correct, l'invalide immédiatement (single-use).
    Retourne True si valide, False sinon.
    """
    r = _get_redis()
    key = _otp_key(phone)
    stored_hash = r.get(key)

    if not stored_hash:
        return False  # expiré ou inexistant

    if stored_hash != _hash_otp(otp):
        return False

    # Invalider après usage
    r.delete(key)
    return True


def send_otp_sms(phone: str, otp: str) -> None:
    """
    Stub SMS — à remplacer par l'intégration opérateur (Airtel / Moov).
    En dev, loggue simplement l'OTP.
    """
    import logging
    log = logging.getLogger("otp_sms")
    if settings.ENVIRONMENT == "development":
        log.warning(f"[DEV-ONLY] OTP pour {phone} : {otp}")
    else:
        # TODO: intégrer l'API SMS (Twilio, Africa's Talking, ou opérateur local)
        raise NotImplementedError("Intégration SMS non configurée en production.")
