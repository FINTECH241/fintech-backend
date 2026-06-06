"""
Tests Sprint 1 — Authentification & Onboarding
Utilise une DB SQLite en mémoire + Redis mocké pour s'exécuter sans infra.
"""
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.session import Base, get_db
from app.main import app

# ── Setup DB en mémoire ───────────────────────────────────────────────────────

TEST_DB_URL = "sqlite:///./test_sprint1.db"
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
OTP_VALID = "123456"


# ── Mock Redis & SMS ──────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def mock_redis_and_sms():
    """Remplace Redis et l'envoi SMS dans tous les tests."""
    store = {}

    class FakeRedis:
        def get(self, key):
            import time
            entry = store.get(key)
            if entry and entry["exp"] > time.time():
                return entry["val"]
            return None

        def setex(self, key, seconds, val):
            import time
            store[key] = {"val": val, "exp": time.time() + seconds}

        def delete(self, key):
            store.pop(key, None)

        def incr(self, key):
            entry = store.get(key, {"val": "0", "exp": float("inf")})
            new_val = str(int(entry["val"]) + 1)
            store[key] = {"val": new_val, "exp": entry["exp"]}
            return int(new_val)

        def expire(self, key, seconds):
            import time
            if key in store:
                store[key]["exp"] = time.time() + seconds

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
         patch("app.services.otp_service.send_otp_sms") as mock_sms, \
         patch("app.services.otp_service.random.SystemRandom") as mock_rand:
        mock_rand.return_value.randint.return_value = int(OTP_VALID)
        yield mock_sms


# ── Tests US-1.1 ──────────────────────────────────────────────────────────────

def test_register_without_consent_fails():
    r = client.post("/api/v1/auth/register", json={"phone": PHONE, "consent": False})
    assert r.status_code == 422


def test_register_sends_otp():
    r = client.post("/api/v1/auth/register", json={"phone": PHONE, "consent": True})
    assert r.status_code == 201
    assert "OTP" in r.json()["message"]


def test_register_verify_wrong_otp():
    client.post("/api/v1/auth/register", json={"phone": PHONE, "consent": True})
    r = client.post("/api/v1/auth/register/verify", json={"phone": PHONE, "otp": "000000"})
    assert r.status_code == 400


def test_register_verify_correct_otp():
    client.post("/api/v1/auth/register", json={"phone": PHONE, "consent": True})
    r = client.post("/api/v1/auth/register/verify", json={"phone": PHONE, "otp": OTP_VALID})
    assert r.status_code == 200


def test_register_duplicate_verified_phone():
    # Après vérification réussie, une 2e inscription doit être refusée
    r = client.post("/api/v1/auth/register", json={"phone": PHONE, "consent": True})
    assert r.status_code == 409


# ── Tests US-1.2 ──────────────────────────────────────────────────────────────

def _login():
    client.post("/api/v1/auth/login/send-otp", json={"phone": PHONE})
    return client.post("/api/v1/auth/login", json={"phone": PHONE, "otp": OTP_VALID})


def test_login_success():
    r = _login()
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    assert "refresh_token" in data


def test_login_wrong_otp():
    client.post("/api/v1/auth/login/send-otp", json={"phone": PHONE})
    r = client.post("/api/v1/auth/login", json={"phone": PHONE, "otp": "000000"})
    assert r.status_code == 401


def test_token_refresh():
    login_r = _login()
    refresh_token = login_r.json()["refresh_token"]
    r = client.post("/api/v1/auth/token/refresh", json={"refresh_token": refresh_token})
    assert r.status_code == 200
    assert "access_token" in r.json()


def test_refresh_token_single_use():
    """Un refresh token ne peut être utilisé qu'une seule fois (rotation)."""
    login_r = _login()
    rt = login_r.json()["refresh_token"]
    client.post("/api/v1/auth/token/refresh", json={"refresh_token": rt})
    r2 = client.post("/api/v1/auth/token/refresh", json={"refresh_token": rt})
    assert r2.status_code == 401


def test_logout_revokes_token():
    login_r = _login()
    at = login_r.json()["access_token"]
    rt = login_r.json()["refresh_token"]
    headers = {"Authorization": f"Bearer {at}"}
    r = client.post("/api/v1/auth/logout", json={"refresh_token": rt}, headers=headers)
    assert r.status_code == 200
    # Après logout, le refresh token ne fonctionne plus
    r2 = client.post("/api/v1/auth/token/refresh", json={"refresh_token": rt})
    assert r2.status_code == 401


# ── Tests US-1.3 ──────────────────────────────────────────────────────────────

def _get_headers():
    r = _login()
    at = r.json()["access_token"]
    return {"Authorization": f"Bearer {at}"}


def test_get_profile():
    r = client.get("/api/v1/auth/profile", headers=_get_headers())
    assert r.status_code == 200
    assert r.json()["phone"] == PHONE


def test_update_profile():
    r = client.patch(
        "/api/v1/auth/profile",
        json={"full_name": "Marie Nguema", "date_of_birth": "1990-05-15"},
        headers=_get_headers(),
    )
    assert r.status_code == 200
    assert r.json()["full_name"] == "Marie Nguema"


def test_update_profile_invalid_dob():
    r = client.patch(
        "/api/v1/auth/profile",
        json={"date_of_birth": "15/05/1990"},
        headers=_get_headers(),
    )
    assert r.status_code == 422
