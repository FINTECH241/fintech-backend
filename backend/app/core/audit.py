"""
Audit Trail — Sprint 1 fondation.
Chaque appel écrit une ligne JSON dans audit.log ET en base (table audit_logs).
Le rattraper plus tard coûte cher → on le pose dès maintenant.
"""
import json
import logging
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session

logger = logging.getLogger("audit")
logger.setLevel(logging.INFO)

_handler = logging.FileHandler("audit.log")
_handler.setFormatter(logging.Formatter("%(message)s"))
logger.addHandler(_handler)


def log_event(
    db: Session,
    event: str,
    user_id: Optional[int] = None,
    phone: Optional[str] = None,
    ip: Optional[str] = None,
    details: Optional[dict] = None,
    success: bool = True,
) -> None:
    """
    Enregistre un événement d'audit.

    Événements utilisés dans Sprint 1 :
      REGISTER_OTP_SENT, REGISTER_OTP_VERIFIED, REGISTER_COMPLETE,
      LOGIN_SUCCESS, LOGIN_FAILED, LOGIN_LOCKED,
      TOKEN_REFRESH, TOKEN_REVOKE,
      PROFILE_UPDATED, CONSENT_RECORDED
    """
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": event,
        "user_id": user_id,
        "phone": phone,
        "ip": ip,
        "success": success,
        "details": details or {},
    }
    logger.info(json.dumps(entry, ensure_ascii=False))

    # Persistance en base
    try:
        from app.models.audit import AuditLog  # import tardif pour éviter circulaire
        db.add(AuditLog(**entry))
        db.commit()
    except Exception as exc:  # ne jamais bloquer la requête pour un log
        logger.error(f"audit_db_error: {exc}")
