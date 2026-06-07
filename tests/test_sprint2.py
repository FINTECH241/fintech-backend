"""
Tests Sprint 2 — KYC Intelligent
Utilise une DB SQLite en mémoire + mocks Tesseract et Smile ID pour s'exécuter sans infra.
"""
import pytest
import base64
import os
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.session import Base, get_db
from app.main import app

# ── Setup DB en mémoire ───────────────────────────────────────────────────────

TEST_DB_URL = "sqlite:///./test_sprint2.db"
engine_test = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine_test)


def override_get_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
Base.metadata.create_all(bind=engine_test)

client = TestClient(app)

PHONE = "+24101234567"


FAKE_ID_IMAGE_B64 = base64.b64encode(
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00"
    b"\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18"
    b"\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
).decode()

FAKE_SELFIE_B64 = FAKE_ID_IMAGE_B64  # même image pour les tests


# ── Helper : créer et authentifier un utilisateur ────────────────────────────

@pytest.fixture(scope="module")
def auth_headers():
    """Inscrit + vérifie + connecte un utilisateur, retourne ses headers JWT."""
    otp_store = {}

    class FakeRedis:
        def get(self, key):
            import time
            entry = otp_store.get(key)
            if entry and entry["exp"] > time.time():
                return entry["val"]
            return None

        def setex(self, key, seconds, val):
            import time
            otp_store[key] = {"val": val, "exp": time.time() + seconds}

        def delete(self, key):
            otp_store.pop(key, None)

        def incr(self, key):
            entry = otp_store.get(key, {"val": "0", "exp": float("inf")})
            new_val = str(int(entry["val"]) + 1)
            otp_store[key] = {"val": new_val, "exp": entry["exp"]}
            return int(new_val)

        def expire(self, key, seconds):
            import time
            if key in otp_store:
                otp_store[key]["exp"] = time.time() + seconds

        def pipeline(self):
            return FakePipeline(self)

    class FakePipeline:
        def __init__(self, r):
            self._r = r
            self._cmds = []

        def incr(self, key):
            self._cmds.append(("incr", key))
            return self

        def expire(self, key, sec):
            self._cmds.append(("expire", key, sec))
            return self

        def execute(self):
            for cmd in self._cmds:
                if cmd[0] == "incr":
                    self._r.incr(cmd[1])
                elif cmd[0] == "expire":
                    self._r.expire(cmd[1], cmd[2])

    with patch("app.services.otp_service._get_redis", return_value=FakeRedis()), \
         patch("app.services.otp_service.send_otp_sms"), \
         patch("app.services.otp_service.random.SystemRandom") as mock_rand:
        mock_rand.return_value.randint.return_value = 123456

        client.post("/api/v1/auth/register", json={"phone": PHONE, "consent": True})
        client.post("/api/v1/auth/register/verify", json={"phone": PHONE, "otp": "123456"})

        client.post("/api/v1/auth/login/send-otp", json={"phone": PHONE})
        login_r = client.post("/api/v1/auth/login", json={"phone": PHONE, "otp": "123456"})
        at = login_r.json()["access_token"]

    return {"Authorization": f"Bearer {at}"}


# ── Mock Tesseract (OCR) & Smile ID (faciale) ─────────────────────────────────

@pytest.fixture(autouse=True)
def mock_external_services():
    """
    Remplace Tesseract et le client Smile ID dans tous les tests KYC.
    - OCR retourne des champs CNI valides par défaut.
    - Smile ID retourne un score de correspondance configurable.
    """
    ocr_result = {
        "last_name": "NGUEMA",
        "first_name": "Marie",
        "date_of_birth": "1990-05-15",
        "document_number": "CNI123456",
        "document_type": "CNI",
        "expiry_date": "2030-05-14",
    }
    smile_result = {
        "match": True,
        "confidence": 0.92,
        "liveness_passed": True,
    }

    with patch("app.services.kyc_service.run_ocr", return_value=ocr_result) as mock_ocr, \
         patch("app.services.kyc_service.smile_id_verify", return_value=smile_result) as mock_smile:
        yield {"ocr": mock_ocr, "smile": mock_smile}


# ── Tests US-2.1 : OCR pièce d'identité ──────────────────────────────────────

def test_upload_id_document_returns_extracted_fields(auth_headers):
    """Une image valide doit retourner les champs OCR extraits."""
    r = client.post(
        "/api/v1/kyc/document",
        json={"image_b64": FAKE_ID_IMAGE_B64, "document_type": "CNI"},
        headers=auth_headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["last_name"] == "NGUEMA"
    assert data["first_name"] == "Marie"
    assert data["document_number"] == "CNI123456"
    assert "document_type" in data
    assert "expiry_date" in data


def test_upload_id_document_unreadable_image(auth_headers, mock_external_services):
    """Une image illisible doit être rejetée avec un message clair."""
    mock_external_services["ocr"].return_value = None  # OCR ne trouve rien

    r = client.post(
        "/api/v1/kyc/document",
        json={"image_b64": FAKE_ID_IMAGE_B64, "document_type": "CNI"},
        headers=auth_headers,
    )
    assert r.status_code == 422
    assert "illisible" in r.json()["detail"].lower() or "unreadable" in r.json()["detail"].lower()


def test_upload_id_document_supported_types(auth_headers):
    """Les types CNI, passeport et carte de séjour sont acceptés."""
    for doc_type in ["CNI", "PASSEPORT", "CARTE_SEJOUR"]:
        r = client.post(
            "/api/v1/kyc/document",
            json={"image_b64": FAKE_ID_IMAGE_B64, "document_type": doc_type},
            headers=auth_headers,
        )
        assert r.status_code == 200, f"Type {doc_type} refusé à tort"


def test_upload_id_document_unsupported_type(auth_headers):
    """Un type de document inconnu doit être rejeté."""
    r = client.post(
        "/api/v1/kyc/document",
        json={"image_b64": FAKE_ID_IMAGE_B64, "document_type": "PERMIS"},
        headers=auth_headers,
    )
    assert r.status_code == 422


def test_upload_id_document_missing_image(auth_headers):
    """Un appel sans image doit retourner 422."""
    r = client.post(
        "/api/v1/kyc/document",
        json={"document_type": "CNI"},
        headers=auth_headers,
    )
    assert r.status_code == 422


def test_correct_ocr_fields_and_confirm(auth_headers):
    
    client.post(
        "/api/v1/kyc/document",
        json={"image_b64": FAKE_ID_IMAGE_B64, "document_type": "CNI"},
        headers=auth_headers,
    )
    
    r = client.patch(
        "/api/v1/kyc/document",
        json={"first_name": "Marie-Claire", "last_name": "NGUEMA"},
        headers=auth_headers,
    )
    assert r.status_code == 200
    assert r.json()["first_name"] == "Marie-Claire"


def test_upload_id_requires_auth():
    """Sans token, l'upload doit être refusé."""
    r = client.post(
        "/api/v1/kyc/document",
        json={"image_b64": FAKE_ID_IMAGE_B64, "document_type": "CNI"},
    )
    assert r.status_code == 401


# ── Tests US-2.2 : Selfie & vérification faciale ─────────────────────────────

def test_selfie_match_success(auth_headers):
    """Un selfie correspondant à la pièce doit passer la vérification."""
    r = client.post(
        "/api/v1/kyc/selfie",
        json={"selfie_b64": FAKE_SELFIE_B64},
        headers=auth_headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["match"] is True
    assert "confidence" in data


def test_selfie_match_below_threshold(auth_headers, mock_external_services):
    """Un score de correspondance trop faible doit déclencher un rejet ou une revue manuelle."""
    mock_external_services["smile"].return_value = {
        "match": False,
        "confidence": 0.41,
        "liveness_passed": True,
    }
    r = client.post(
        "/api/v1/kyc/selfie",
        json={"selfie_b64": FAKE_SELFIE_B64},
        headers=auth_headers,
    )
   
    assert r.status_code in (200, 202)
    data = r.json()
    assert data.get("kyc_status") in ("rejected", "pending_review")


def test_selfie_liveness_failed(auth_headers, mock_external_services):
    """Une détection de vivacité échouée (photo d'une photo) doit être rejetée."""
    mock_external_services["smile"].return_value = {
        "match": True,
        "confidence": 0.95,
        "liveness_passed": False,
    }
    r = client.post(
        "/api/v1/kyc/selfie",
        json={"selfie_b64": FAKE_SELFIE_B64},
        headers=auth_headers,
    )
    assert r.status_code == 400
    assert "liveness" in r.json()["detail"].lower() or "vivacité" in r.json()["detail"].lower()


def test_selfie_requires_document_upload_first(auth_headers, mock_external_services):
    """Le selfie ne peut pas être soumis sans avoir d'abord uploadé la pièce d'identité."""
    
    mock_external_services["ocr"].return_value = None

    new_phone = "+24109999999"
    
    with patch("app.services.otp_service._get_redis", return_value=MagicMock(
        get=lambda k: None, setex=lambda k, s, v: None,
        delete=lambda k: None, incr=lambda k: 1, expire=lambda k, s: None,
        pipeline=lambda: MagicMock(incr=lambda k: MagicMock(expire=lambda k, s: MagicMock(execute=lambda: None)))
    )), patch("app.services.otp_service.send_otp_sms"), \
       patch("app.services.otp_service.random.SystemRandom") as mr:
        mr.return_value.randint.return_value = 654321
        client.post("/api/v1/auth/register", json={"phone": new_phone, "consent": True})
        client.post("/api/v1/auth/register/verify", json={"phone": new_phone, "otp": "654321"})
        client.post("/api/v1/auth/login/send-otp", json={"phone": new_phone})
        lr = client.post("/api/v1/auth/login", json={"phone": new_phone, "otp": "654321"})

    new_headers = {"Authorization": f"Bearer {lr.json()['access_token']}"}
    r = client.post(
        "/api/v1/kyc/selfie",
        json={"selfie_b64": FAKE_SELFIE_B64},
        headers=new_headers,
    )
    assert r.status_code == 400


def test_selfie_missing_image(auth_headers):
    """Un appel selfie sans image doit retourner 422."""
    r = client.post("/api/v1/kyc/selfie", json={}, headers=auth_headers)
    assert r.status_code == 422


def test_selfie_requires_auth():
    """Sans token, le selfie doit être refusé."""
    r = client.post("/api/v1/kyc/selfie", json={"selfie_b64": FAKE_SELFIE_B64})
    assert r.status_code == 401


# ── Tests US-2.3 : File d'attente admin & arbitrage ───────────────────────────

@pytest.fixture(scope="module")
def admin_headers():
    """Retourne les headers d'un utilisateur admin."""
    
    admin_phone = "+24100000001"

    with patch("app.services.otp_service._get_redis", return_value=MagicMock(
        get=lambda k: None, setex=lambda k, s, v: None,
        delete=lambda k: None, incr=lambda k: 1, expire=lambda k, s: None,
        pipeline=lambda: MagicMock(incr=lambda k: MagicMock(expire=lambda k, s: MagicMock(execute=lambda: None)))
    )), patch("app.services.otp_service.send_otp_sms"), \
       patch("app.services.otp_service.random.SystemRandom") as mr:
        mr.return_value.randint.return_value = 111111
        client.post("/api/v1/auth/register", json={"phone": admin_phone, "consent": True})
        client.post("/api/v1/auth/register/verify", json={"phone": admin_phone, "otp": "111111"})
        client.post("/api/v1/auth/login/send-otp", json={"phone": admin_phone})
        lr = client.post("/api/v1/auth/login", json={"phone": admin_phone, "otp": "111111"})

    return {"Authorization": f"Bearer {lr.json()['access_token']}"}


def _push_to_review_queue(auth_headers, mock_external_services):
    """Place un dossier en zone grise (score intermédiaire)."""
    mock_external_services["smile"].return_value = {
        "match": True,
        "confidence": 0.65,   
        "liveness_passed": True,
    }
    client.post(
        "/api/v1/kyc/document",
        json={"image_b64": FAKE_ID_IMAGE_B64, "document_type": "CNI"},
        headers=auth_headers,
    )
    r = client.post(
        "/api/v1/kyc/selfie",
        json={"selfie_b64": FAKE_SELFIE_B64},
        headers=auth_headers,
    )
    assert r.status_code == 202  
    return r.json().get("kyc_id")


def test_admin_can_list_pending_reviews(auth_headers, admin_headers, mock_external_services):
    """Un admin peut lister les dossiers en attente de revue manuelle."""
    _push_to_review_queue(auth_headers, mock_external_services)

    r = client.get("/api/v1/admin/kyc/queue", headers=admin_headers)
    assert r.status_code == 200
    items = r.json()
    assert isinstance(items, list)
    assert len(items) >= 1
    first = items[0]
    assert "kyc_id" in first
    assert "phone" in first or "user_id" in first
    assert first.get("status") == "pending_review"


def test_admin_approve_dossier(auth_headers, admin_headers, mock_external_services):
    """Un admin peut approuver manuellement un dossier en zone grise."""
    kyc_id = _push_to_review_queue(auth_headers, mock_external_services)

    r = client.post(
        f"/api/v1/admin/kyc/{kyc_id}/decision",
        json={"decision": "approved", "reason": "Documents conformes après vérification manuelle."},
        headers=admin_headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["kyc_status"] == "verified"
   
    assert "decided_by" in data
    assert "decided_at" in data
    assert "reason" in data


def test_admin_reject_dossier(auth_headers, admin_headers, mock_external_services):
    """Un admin peut rejeter manuellement un dossier."""
    kyc_id = _push_to_review_queue(auth_headers, mock_external_services)

    r = client.post(
        f"/api/v1/admin/kyc/{kyc_id}/decision",
        json={"decision": "rejected", "reason": "Photo floue, identité non vérifiable."},
        headers=admin_headers,
    )
    assert r.status_code == 200
    assert r.json()["kyc_status"] == "rejected"


def test_admin_decision_requires_reason(auth_headers, admin_headers, mock_external_services):
    """Une décision admin sans motif doit être refusée."""
    kyc_id = _push_to_review_queue(auth_headers, mock_external_services)

    r = client.post(
        f"/api/v1/admin/kyc/{kyc_id}/decision",
        json={"decision": "approved"},
        headers=admin_headers,
    )
    assert r.status_code == 422


def test_admin_decision_invalid_value(auth_headers, admin_headers, mock_external_services):
    """Une valeur de décision invalide doit être rejetée."""
    kyc_id = _push_to_review_queue(auth_headers, mock_external_services)

    r = client.post(
        f"/api/v1/admin/kyc/{kyc_id}/decision",
        json={"decision": "maybe", "reason": "Pas sûr."},
        headers=admin_headers,
    )
    assert r.status_code == 422


def test_admin_decision_traces_who_decided(auth_headers, admin_headers, mock_external_services):
    """La décision admin doit enregistrer l'identité de l'admin (qui, quand)."""
    kyc_id = _push_to_review_queue(auth_headers, mock_external_services)

    r = client.post(
        f"/api/v1/admin/kyc/{kyc_id}/decision",
        json={"decision": "approved", "reason": "Vérification manuelle OK."},
        headers=admin_headers,
    )
    data = r.json()
    assert data["decided_by"] is not None    
    assert data["decided_at"] is not None    
    assert data["reason"] == "Vérification manuelle OK."


def test_non_admin_cannot_access_queue(auth_headers):
    """Un utilisateur standard ne peut pas accéder à la file d'attente admin."""
    r = client.get("/api/v1/admin/kyc/queue", headers=auth_headers)
    assert r.status_code in (401, 403)


def test_non_admin_cannot_make_decision(auth_headers, mock_external_services):
    """Un utilisateur standard ne peut pas prendre de décision admin."""
    r = client.post(
        "/api/v1/admin/kyc/fake-id/decision",
        json={"decision": "approved", "reason": "Tentative non autorisée."},
        headers=auth_headers,
    )
    assert r.status_code in (401, 403)


def test_user_notified_after_admin_decision(auth_headers, admin_headers, mock_external_services):
    """Après une décision admin, le statut KYC de l'utilisateur est mis à jour."""
    kyc_id = _push_to_review_queue(auth_headers, mock_external_services)

    client.post(
        f"/api/v1/admin/kyc/{kyc_id}/decision",
        json={"decision": "approved", "reason": "OK."},
        headers=admin_headers,
    )
   
    r = client.get("/api/v1/kyc/status", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["kyc_status"] == "verified"


# ── Tests statuts KYC globaux ─────────────────────────────────────────────────

def test_kyc_status_pending_before_submission(auth_headers):
    """Avant toute soumission KYC, le statut est 'pending'."""
   
    fresh_phone = "+24108888888"
    with patch("app.services.otp_service._get_redis", return_value=MagicMock(
        get=lambda k: None, setex=lambda k, s, v: None,
        delete=lambda k: None, incr=lambda k: 1, expire=lambda k, s: None,
        pipeline=lambda: MagicMock(incr=lambda k: MagicMock(expire=lambda k, s: MagicMock(execute=lambda: None)))
    )), patch("app.services.otp_service.send_otp_sms"), \
       patch("app.services.otp_service.random.SystemRandom") as mr:
        mr.return_value.randint.return_value = 777777
        client.post("/api/v1/auth/register", json={"phone": fresh_phone, "consent": True})
        client.post("/api/v1/auth/register/verify", json={"phone": fresh_phone, "otp": "777777"})
        client.post("/api/v1/auth/login/send-otp", json={"phone": fresh_phone})
        lr = client.post("/api/v1/auth/login", json={"phone": fresh_phone, "otp": "777777"})

    fresh_headers = {"Authorization": f"Bearer {lr.json()['access_token']}"}
    r = client.get("/api/v1/kyc/status", headers=fresh_headers)
    assert r.status_code == 200
    assert r.json()["kyc_status"] == "pending"


def test_kyc_status_verified_after_auto_approval(auth_headers, mock_external_services):
    """Avec un score élevé, le statut passe directement à 'verified' sans revue manuelle."""
    mock_external_services["smile"].return_value = {
        "match": True,
        "confidence": 0.95,
        "liveness_passed": True,
    }
    client.post(
        "/api/v1/kyc/document",
        json={"image_b64": FAKE_ID_IMAGE_B64, "document_type": "CNI"},
        headers=auth_headers,
    )
    r = client.post(
        "/api/v1/kyc/selfie",
        json={"selfie_b64": FAKE_SELFIE_B64},
        headers=auth_headers,
    )
    assert r.status_code == 200
    assert r.json()["kyc_status"] == "verified"
