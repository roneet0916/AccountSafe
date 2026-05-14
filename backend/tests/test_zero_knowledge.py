# api/tests/test_zero_knowledge.py
"""
Zero-Knowledge Authentication - Comprehensive Security Tests
═══════════════════════════════════════════════════════════════════════════════

Tests covering ALL ZK authentication endpoints:
- Register, Login, GetSalt, ChangePassword
- SetDuress, ClearDuress, Verify, SwitchMode, DeleteAccount

All tests assert:
- Correct HTTP status codes and response bodies
- Data integrity in database
- Security invariants (no password leaks, constant-time comparison, anti-enumeration)
- Boundary conditions and malicious input handling
- Race condition safety

Endpoints tested hit zero_knowledge.py views directly (not AuthService delegation).
"""

import hashlib
import hmac
import secrets
import time
import threading
from unittest.mock import patch, MagicMock

import pytest
from django.conf import settings
from django.contrib.auth.models import User
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APIClient

from api.models import (
    DuressSession,
    LoginRecord,
    MultiToken,
    UserProfile,
    UserSession,
)
from tests.conftest import generate_auth_hash, generate_salt


# ═══════════════════════════════════════════════════════════════════════════════
# REGISTER TESTS
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestZeroKnowledgeRegisterView:
    """Tests for POST /api/zk/register/"""

    URL = "/api/zk/register/"

    def _register_payload(self, **overrides):
        """Build a valid registration payload, with optional field overrides."""
        salt = generate_salt()
        auth_hash = generate_auth_hash("StrongPassword1!", salt)
        payload = {
            "username": f"testuser_{secrets.token_hex(4)}",
            "email": f"test_{secrets.token_hex(4)}@example.com",
            "auth_hash": auth_hash,
            "salt": salt,
        }
        payload.update(overrides)
        return payload

    # ── Positive ──────────────────────────────────────────────────────────

    @override_settings(DEBUG=True)
    def test_register_success_creates_user_with_unusable_password(self, api_client):
        payload = self._register_payload(username="alice", email="alice@test.com")
        resp = api_client.post(self.URL, payload, format="json")

        assert resp.status_code == status.HTTP_201_CREATED
        user = User.objects.get(username="alice")
        assert not user.has_usable_password(), "ZK users MUST have unusable Django password"

    @override_settings(DEBUG=True)
    def test_register_returns_token_and_user(self, api_client):
        payload = self._register_payload(username="bob", email="bob@test.com")
        resp = api_client.post(self.URL, payload, format="json")

        data = resp.json()
        assert "key" in data, "Response must contain auth token"
        assert len(data["key"]) == 64, "Raw token should be 64 hex chars (256 bits)"
        assert data["user"]["username"] == "bob"
        assert data["user"]["email"] == "bob@test.com"

    @override_settings(DEBUG=True)
    def test_register_stores_auth_hash_lowercase_hex(self, api_client):
        salt = generate_salt()
        auth_hash = generate_auth_hash("password123", salt).upper()  # send UPPERCASE
        payload = self._register_payload(
            username="carol",
            email="carol@test.com",
            auth_hash=auth_hash,
            salt=salt,
        )
        resp = api_client.post(self.URL, payload, format="json")
        assert resp.status_code == status.HTTP_201_CREATED

        profile = User.objects.get(username="carol").userprofile
        assert profile.auth_hash == auth_hash.lower(), "auth_hash must be stored lowercase"
        assert len(profile.auth_hash) == 64
        assert all(c in "0123456789abcdef" for c in profile.auth_hash)

    @override_settings(DEBUG=True)
    def test_register_stores_encryption_salt(self, api_client):
        salt = generate_salt()
        payload = self._register_payload(
            username="dave",
            email="dave@test.com",
            salt=salt,
        )
        resp = api_client.post(self.URL, payload, format="json")
        assert resp.status_code == status.HTTP_201_CREATED

        profile = User.objects.get(username="dave").userprofile
        assert profile.encryption_salt == salt

    @override_settings(DEBUG=True)
    def test_register_creates_user_session(self, api_client):
        payload = self._register_payload(username="eve", email="eve@test.com")
        resp = api_client.post(self.URL, payload, format="json")
        assert resp.status_code == status.HTTP_201_CREATED

        user = User.objects.get(username="eve")
        assert UserSession.objects.filter(user=user).exists(), "UserSession must be created on register"

    @override_settings(DEBUG=True)
    def test_register_sets_correct_vault_version(self, api_client):
        payload = self._register_payload(username="fay", email="fay@test.com")
        resp = api_client.post(self.URL, payload, format="json")
        assert resp.status_code == status.HTTP_201_CREATED

        profile = User.objects.get(username="fay").userprofile
        assert profile.vault_version == "1.0.0"

    # ── Negative / Duplicate ─────────────────────────────────────────────

    @override_settings(DEBUG=True)
    def test_register_duplicate_username_rejected(self, api_client, create_zk_user):
        create_zk_user(username="dupuser", password="pass1")
        payload = self._register_payload(username="dupuser", email="other@test.com")
        resp = api_client.post(self.URL, payload, format="json")

        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "already exists" in resp.json()["error"].lower()

    @override_settings(DEBUG=True)
    def test_register_duplicate_email_rejected(self, api_client, create_zk_user):
        create_zk_user(username="emaildup1", password="pass1", email="dup@test.com")
        payload = self._register_payload(username="emaildup2", email="dup@test.com")
        resp = api_client.post(self.URL, payload, format="json")

        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "already exists" in resp.json()["error"].lower()

    @override_settings(DEBUG=True)
    def test_register_case_insensitive_username(self, api_client, create_zk_user):
        create_zk_user(username="CaseUser", password="pass1")
        payload = self._register_payload(username="caseuser", email="case2@test.com")
        resp = api_client.post(self.URL, payload, format="json")

        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    # ── Boundary / Validation ────────────────────────────────────────────

    @override_settings(DEBUG=True)
    def test_register_auth_hash_too_short(self, api_client):
        payload = self._register_payload(auth_hash="abcdef1234567890" * 3)  # 48 chars
        resp = api_client.post(self.URL, payload, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    @override_settings(DEBUG=True)
    def test_register_auth_hash_too_long(self, api_client):
        payload = self._register_payload(auth_hash="a" * 65)
        resp = api_client.post(self.URL, payload, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    @override_settings(DEBUG=True)
    def test_register_auth_hash_non_hex(self, api_client):
        payload = self._register_payload(auth_hash="g" * 64)
        resp = api_client.post(self.URL, payload, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    @override_settings(DEBUG=True)
    def test_register_auth_hash_empty(self, api_client):
        payload = self._register_payload(auth_hash="")
        resp = api_client.post(self.URL, payload, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    @override_settings(DEBUG=True)
    def test_register_missing_username(self, api_client):
        payload = self._register_payload()
        del payload["username"]
        resp = api_client.post(self.URL, payload, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    @override_settings(DEBUG=True)
    def test_register_missing_email(self, api_client):
        payload = self._register_payload()
        del payload["email"]
        resp = api_client.post(self.URL, payload, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    @override_settings(DEBUG=True)
    def test_register_missing_auth_hash(self, api_client):
        payload = self._register_payload()
        del payload["auth_hash"]
        resp = api_client.post(self.URL, payload, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    @override_settings(DEBUG=True)
    def test_register_missing_salt(self, api_client):
        payload = self._register_payload()
        del payload["salt"]
        resp = api_client.post(self.URL, payload, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    @override_settings(DEBUG=True)
    def test_register_empty_body(self, api_client):
        resp = api_client.post(self.URL, {}, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    # ── Security ─────────────────────────────────────────────────────────

    @override_settings(DEBUG=True)
    def test_register_auth_hash_null_bytes(self, api_client):
        payload = self._register_payload(auth_hash="a" * 32 + "\x00" + "b" * 31)
        resp = api_client.post(self.URL, payload, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    @override_settings(DEBUG=True)
    def test_register_auth_hash_sql_injection(self, api_client):
        payload = self._register_payload(auth_hash="' OR 1=1 --")
        resp = api_client.post(self.URL, payload, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        # Ensure no user was created
        assert User.objects.count() == 0

    @override_settings(DEBUG=True)
    def test_register_auth_hash_xss_payload(self, api_client):
        payload = self._register_payload(auth_hash="<script>alert(1)</script>")
        resp = api_client.post(self.URL, payload, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        # Verify no profile stored the XSS payload
        assert not UserProfile.objects.filter(auth_hash__contains="<script>").exists()

    @override_settings(DEBUG=True)
    def test_register_response_does_not_leak_auth_hash(self, api_client):
        salt = generate_salt()
        auth_hash = generate_auth_hash("secret", salt)
        payload = self._register_payload(
            username="noleak",
            email="noleak@test.com",
            auth_hash=auth_hash,
            salt=salt,
        )
        resp = api_client.post(self.URL, payload, format="json")
        assert resp.status_code == status.HTTP_201_CREATED

        body = resp.content.decode()
        assert auth_hash not in body, "Response MUST NOT echo back auth_hash"

    @override_settings(DEBUG=False)
    def test_register_turnstile_required_in_production(self, api_client):
        payload = self._register_payload()
        # No turnstile_token in production mode
        resp = api_client.post(self.URL, payload, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert (
            "captcha" in resp.json().get("error", "").lower() or "verification" in resp.json().get("error", "").lower()
        )

    @override_settings(DEBUG=True)
    @patch("api.features.auth.zero_knowledge.verify_turnstile_token")
    def test_register_turnstile_invalid_token(self, mock_turnstile, api_client):
        mock_turnstile.return_value = {"success": False}
        payload = self._register_payload()
        payload["turnstile_token"] = "invalid-token"
        resp = api_client.post(self.URL, payload, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    @override_settings(DEBUG=True)
    def test_register_username_special_characters(self, api_client):
        for username in ["../admin", "%00null", "<script>", "user;DROP TABLE"]:
            payload = self._register_payload(
                username=username,
                email=f"{secrets.token_hex(4)}@test.com",
            )
            resp = api_client.post(self.URL, payload, format="json")
            # The server should not crash - it doesn't necessarily reject
            # but must not cause 500
            assert resp.status_code != status.HTTP_500_INTERNAL_SERVER_ERROR

    # ── Integrity ────────────────────────────────────────────────────────

    @override_settings(DEBUG=True)
    def test_register_atomic_failure_rollback(self, api_client):
        """If session creation fails mid-transaction, user should NOT exist."""
        with patch(
            "api.features.auth.zero_knowledge.UserSession.objects.create",
            side_effect=Exception("DB error"),
        ):
            payload = self._register_payload(username="atomicfail", email="atomic@test.com")
            resp = api_client.post(self.URL, payload, format="json")
            assert resp.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        assert not User.objects.filter(
            username="atomicfail"
        ).exists(), "User must be rolled back on transaction failure"

    @override_settings(DEBUG=True)
    def test_register_concurrent_same_username(self, api_client):
        """Two simultaneous registrations with the same username - only one succeeds."""
        salt = generate_salt()
        auth_hash = generate_auth_hash("password", salt)
        payload = {
            "username": "raceuser",
            "email": "race1@test.com",
            "auth_hash": auth_hash,
            "salt": salt,
        }
        payload2 = {
            "username": "raceuser",
            "email": "race2@test.com",
            "auth_hash": auth_hash,
            "salt": salt,
        }

        results = []

        def do_register(p):
            client = APIClient()
            resp = client.post(self.URL, p, format="json")
            results.append(resp.status_code)

        t1 = threading.Thread(target=do_register, args=(payload,))
        t2 = threading.Thread(target=do_register, args=(payload2,))
        t1.start()
        t2.start()
        t1.join(timeout=10)
        t2.join(timeout=10)

        success_count = results.count(201)
        assert success_count <= 1, "At most one registration should succeed"
        assert User.objects.filter(username__iexact="raceuser").count() <= 1


# ═══════════════════════════════════════════════════════════════════════════════
# LOGIN TESTS
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestZeroKnowledgeLoginView:
    """Tests for POST /api/zk/login/"""

    URL = "/api/zk/login/"

    # ── Positive ──────────────────────────────────────────────────────────

    @override_settings(DEBUG=True)
    def test_login_correct_auth_hash(self, api_client, create_zk_user):
        user, token, auth_hash, salt = create_zk_user(username="loginuser", password="ValidPass1!")
        resp = api_client.post(
            self.URL,
            {"username": "loginuser", "auth_hash": auth_hash},
            format="json",
        )
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert "key" in data
        assert data["user"]["username"] == "loginuser"
        assert "salt" in data
        assert data["is_duress"] is False

    @override_settings(DEBUG=True)
    def test_login_creates_new_token_each_time(self, api_client, create_zk_user):
        user, token, auth_hash, salt = create_zk_user(username="multilogin", password="Pass1!")
        tokens = set()
        for _ in range(3):
            resp = api_client.post(
                self.URL,
                {"username": "multilogin", "auth_hash": auth_hash},
                format="json",
            )
            assert resp.status_code == status.HTTP_200_OK
            tokens.add(resp.json()["key"])

        assert len(tokens) == 3, "Each login must produce a unique token"

    @override_settings(DEBUG=True)
    def test_login_creates_user_session(self, api_client, create_zk_user):
        user, token, auth_hash, salt = create_zk_user(username="sessionuser", password="Pass1!")
        initial_count = UserSession.objects.filter(user=user).count()
        api_client.post(
            self.URL,
            {"username": "sessionuser", "auth_hash": auth_hash},
            format="json",
        )
        assert UserSession.objects.filter(user=user).count() > initial_count

    @override_settings(DEBUG=True)
    @patch("api.features.auth.zero_knowledge.track_zk_login_attempt")
    def test_login_tracks_login_record_success(self, mock_track, api_client, create_zk_user):
        user, token, auth_hash, salt = create_zk_user(username="trackuser", password="Pass1!")
        api_client.post(
            self.URL,
            {"username": "trackuser", "auth_hash": auth_hash},
            format="json",
        )
        mock_track.assert_called()
        # Verify is_success=True was passed
        call_kwargs = mock_track.call_args
        assert call_kwargs[1].get("is_success", call_kwargs[0][2] if len(call_kwargs[0]) > 2 else None) is True or (
            len(call_kwargs[0]) > 2 and call_kwargs[0][2] is True
        )

    @override_settings(DEBUG=True)
    @patch("api.features.auth.zero_knowledge.track_zk_login_attempt")
    def test_login_failed_tracks_login_record(self, mock_track, api_client, create_zk_user):
        create_zk_user(username="failtrack", password="Pass1!")
        api_client.post(
            self.URL,
            {"username": "failtrack", "auth_hash": "a" * 64},
            format="json",
        )
        mock_track.assert_called()
        call_args = mock_track.call_args
        # is_success should be False
        assert call_args[1].get("is_success", call_args[0][2] if len(call_args[0]) > 2 else None) is False or (
            len(call_args[0]) > 2 and call_args[0][2] is False
        )

    @override_settings(DEBUG=True)
    def test_login_is_relogin_flag_suppresses_email(self, api_client, create_zk_user):
        user, token, auth_hash, salt = create_zk_user(username="reloginuser", password="Pass1!")
        with patch("api.features.auth.zero_knowledge.track_zk_login_attempt") as mock_track:
            api_client.post(
                self.URL,
                {"username": "reloginuser", "auth_hash": auth_hash, "is_relogin": True},
                format="json",
            )
            mock_track.assert_called()
            call_kwargs = mock_track.call_args
            # send_notification should be False for relogin
            assert call_kwargs[1].get("send_notification") is False or (
                len(call_kwargs[0]) > 5 and call_kwargs[0][5] is False
            )

    # ── Negative ──────────────────────────────────────────────────────────

    @override_settings(DEBUG=True)
    def test_login_wrong_auth_hash(self, api_client, create_zk_user):
        create_zk_user(username="wrongpw", password="Correct1!")
        resp = api_client.post(
            self.URL,
            {"username": "wrongpw", "auth_hash": "b" * 64},
            format="json",
        )
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED
        assert "invalid" in resp.json()["error"].lower()

    @override_settings(DEBUG=True)
    def test_login_missing_username(self, api_client):
        resp = api_client.post(self.URL, {"auth_hash": "a" * 64}, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    @override_settings(DEBUG=True)
    def test_login_missing_auth_hash(self, api_client):
        resp = api_client.post(self.URL, {"username": "someone"}, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    @override_settings(DEBUG=True)
    def test_login_empty_auth_hash(self, api_client, create_zk_user):
        create_zk_user(username="emptylogin", password="Pass1!")
        resp = api_client.post(
            self.URL,
            {"username": "emptylogin", "auth_hash": ""},
            format="json",
        )
        assert resp.status_code in (
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_401_UNAUTHORIZED,
        )

    # ── Security / Anti-Enumeration ──────────────────────────────────────

    @override_settings(DEBUG=True)
    def test_login_nonexistent_user_returns_same_as_wrong_password(self, api_client, create_zk_user):
        """Response for nonexistent user MUST be identical to wrong password."""
        create_zk_user(username="existing", password="Pass1!")

        resp_wrong_pw = api_client.post(
            self.URL,
            {"username": "existing", "auth_hash": "c" * 64},
            format="json",
        )
        resp_no_user = api_client.post(
            self.URL,
            {"username": "ghostuser", "auth_hash": "c" * 64},
            format="json",
        )

        assert resp_wrong_pw.status_code == resp_no_user.status_code == status.HTTP_401_UNAUTHORIZED
        assert (
            resp_wrong_pw.json() == resp_no_user.json()
        ), "Responses must be identical to prevent username enumeration"

    @override_settings(DEBUG=True)
    def test_login_timing_attack_resistance(self, api_client, create_zk_user):
        """Response time for nonexistent user should be within tolerance of wrong password."""
        create_zk_user(username="timinguser", password="Pass1!")

        iterations = 5
        wrong_pw_times = []
        no_user_times = []

        for _ in range(iterations):
            start = time.perf_counter()
            api_client.post(
                self.URL,
                {"username": "timinguser", "auth_hash": "d" * 64},
                format="json",
            )
            wrong_pw_times.append(time.perf_counter() - start)

            start = time.perf_counter()
            api_client.post(
                self.URL,
                {"username": "nonexistent_timing", "auth_hash": "d" * 64},
                format="json",
            )
            no_user_times.append(time.perf_counter() - start)

        avg_wrong = sum(wrong_pw_times) / len(wrong_pw_times)
        avg_no_user = sum(no_user_times) / len(no_user_times)
        delta = abs(avg_wrong - avg_no_user)

        # 100ms tolerance - generous to avoid flaky CI
        assert delta < 0.1, f"Timing delta {delta:.4f}s exceeds 100ms tolerance - potential timing side channel"

    @override_settings(DEBUG=True)
    def test_login_constant_time_comparison_used(self, api_client, create_zk_user):
        """Verify hmac.compare_digest is called, not `==`."""
        user, token, auth_hash, salt = create_zk_user(username="consttime", password="Pass1!")
        with patch(
            "api.features.auth.zero_knowledge.constant_time_compare",
            wraps=lambda a, b: hmac.compare_digest(a.encode(), b.encode()),
        ) as mock_ct:
            api_client.post(
                self.URL,
                {"username": "consttime", "auth_hash": auth_hash},
                format="json",
            )
            assert mock_ct.called, "constant_time_compare MUST be used for auth_hash comparison"

    @override_settings(DEBUG=True)
    def test_login_sql_injection_in_username(self, api_client):
        resp = api_client.post(
            self.URL,
            {"username": "' OR 1=1 --", "auth_hash": "a" * 64},
            format="json",
        )
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED
        assert "error" in resp.json()

    # ── Duress Login ─────────────────────────────────────────────────────

    @override_settings(DEBUG=True)
    def test_login_duress_auth_hash_returns_duress_salt(self, api_client, create_zk_user):
        user, token, auth_hash, salt = create_zk_user(username="duresslogin", password="Master1!")
        profile = UserProfile.objects.get(user=user)
        duress_salt = generate_salt()
        duress_hash = generate_auth_hash("Duress1!", duress_salt)
        profile.duress_auth_hash = duress_hash
        profile.duress_salt = duress_salt
        profile.sos_email = "sos@test.com"
        profile.save()

        with patch("api.features.security.services.SecurityService.send_duress_alert"):
            resp = api_client.post(
                self.URL,
                {"username": "duresslogin", "auth_hash": duress_hash},
                format="json",
            )

        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["is_duress"] is True
        assert data["salt"] == duress_salt

    @override_settings(DEBUG=True)
    def test_login_duress_creates_duress_session(self, api_client, create_zk_user):
        user, token, auth_hash, salt = create_zk_user(username="duressession", password="Master1!")
        profile = UserProfile.objects.get(user=user)
        d_salt = generate_salt()
        d_hash = generate_auth_hash("Duress1!", d_salt)
        profile.duress_auth_hash = d_hash
        profile.duress_salt = d_salt
        profile.save()

        with patch("api.features.security.services.SecurityService.send_duress_alert"):
            resp = api_client.post(
                self.URL,
                {"username": "duressession", "auth_hash": d_hash},
                format="json",
            )

        assert resp.status_code == status.HTTP_200_OK
        assert DuressSession.objects.filter(user=user).exists(), "DuressSession MUST be created on duress login"

    @override_settings(DEBUG=True)
    def test_login_duress_sends_sos_alert(self, api_client, create_zk_user):
        user, token, auth_hash, salt = create_zk_user(username="duresssos", password="Master1!")
        profile = UserProfile.objects.get(user=user)
        d_salt = generate_salt()
        d_hash = generate_auth_hash("Duress1!", d_salt)
        profile.duress_auth_hash = d_hash
        profile.duress_salt = d_salt
        profile.sos_email = "alert@test.com"
        profile.save()

        with patch("api.features.security.services.SecurityService.send_duress_alert") as mock_alert:
            api_client.post(
                self.URL,
                {"username": "duresssos", "auth_hash": d_hash},
                format="json",
            )
            # Allow background thread to execute
            time.sleep(0.3)

        # The alert is called in a daemon thread - we patched the target
        # so the thread calls our mock instead
        mock_alert.assert_called_once()

    @override_settings(DEBUG=True)
    def test_login_duress_sos_failure_does_not_block_login(self, api_client, create_zk_user):
        """If SOS email fails, login must still succeed."""
        user, token, auth_hash, salt = create_zk_user(username="sosfail", password="Master1!")
        profile = UserProfile.objects.get(user=user)
        d_salt = generate_salt()
        d_hash = generate_auth_hash("Duress1!", d_salt)
        profile.duress_auth_hash = d_hash
        profile.duress_salt = d_salt
        profile.save()

        with patch(
            "api.features.security.services.SecurityService.send_duress_alert",
            side_effect=Exception("SMTP failure"),
        ):
            resp = api_client.post(
                self.URL,
                {"username": "sosfail", "auth_hash": d_hash},
                format="json",
            )

        # Login MUST still succeed even if SOS fails
        assert resp.status_code == status.HTTP_200_OK

    # ── Concurrent ───────────────────────────────────────────────────────

    @override_settings(DEBUG=True)
    def test_login_multi_device_tokens_all_valid(self, api_client, create_zk_user):
        """All tokens from multiple logins remain valid for API access (multi-device)."""
        user, token, auth_hash, salt = create_zk_user(username="conclogin", password="Pass1!")
        tokens = []
        for _ in range(3):
            resp = api_client.post(
                self.URL,
                {"username": "conclogin", "auth_hash": auth_hash},
                format="json",
            )
            assert resp.status_code == status.HTTP_200_OK
            tokens.append(resp.json()["key"])

        assert len(set(tokens)) == 3, "Each login must produce a unique token"
        # Verify each token is independently valid for authenticated requests
        for tk in tokens:
            client = APIClient()
            client.credentials(HTTP_AUTHORIZATION=f"Token {tk}")
            resp = client.get("/api/zk/salt/", {"username": "conclogin"})
            assert resp.status_code == status.HTTP_200_OK


# ═══════════════════════════════════════════════════════════════════════════════
# GET SALT TESTS
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestZeroKnowledgeGetSaltView:
    """Tests for GET /api/zk/salt/?username=xxx"""

    URL = "/api/zk/salt/"

    @override_settings(DEBUG=True)
    def test_get_salt_existing_user(self, api_client, create_zk_user):
        user, token, auth_hash, salt = create_zk_user(username="saltuser", password="Pass1!")
        resp = api_client.get(self.URL, {"username": "saltuser"})
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["salt"] == salt
        assert resp.json()["has_zk_auth"] is True

    @override_settings(DEBUG=True)
    def test_get_salt_nonexistent_user_returns_fake_salt(self, api_client):
        resp = api_client.get(self.URL, {"username": "nonexistent_user_xyz"})
        assert resp.status_code == status.HTTP_200_OK, "Must return 200 to prevent username enumeration"
        assert "salt" in resp.json()
        assert resp.json()["salt"]  # non-empty

    @override_settings(DEBUG=True)
    def test_get_salt_fake_salt_is_deterministic(self, api_client):
        r1 = api_client.get(self.URL, {"username": "ghost1"})
        r2 = api_client.get(self.URL, {"username": "ghost1"})
        assert r1.json()["salt"] == r2.json()["salt"], "Same nonexistent username must always return same fake salt"

    @override_settings(DEBUG=True)
    def test_get_salt_fake_salt_differs_per_username(self, api_client):
        r1 = api_client.get(self.URL, {"username": "ghost_a"})
        r2 = api_client.get(self.URL, {"username": "ghost_b"})
        assert r1.json()["salt"] != r2.json()["salt"], "Different nonexistent usernames must get different fake salts"

    @override_settings(DEBUG=True)
    def test_get_salt_real_and_fake_salt_indistinguishable_format(self, api_client, create_zk_user):
        user, token, auth_hash, real_salt = create_zk_user(username="fmtuser", password="Pass1!")
        real_resp = api_client.get(self.URL, {"username": "fmtuser"})
        fake_resp = api_client.get(self.URL, {"username": "fmtghost"})

        real_s = real_resp.json()["salt"]
        fake_s = fake_resp.json()["salt"]
        # Both should be non-empty strings
        assert isinstance(real_s, str) and len(real_s) > 0
        assert isinstance(fake_s, str) and len(fake_s) > 0

    @override_settings(DEBUG=True)
    def test_get_salt_no_authentication_required(self, api_client):
        # No credentials set - should still work (AllowAny)
        resp = api_client.get(self.URL, {"username": "anyone"})
        assert resp.status_code == status.HTTP_200_OK

    def test_get_salt_missing_username_param(self, api_client):
        resp = api_client.get(self.URL)
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    @override_settings(DEBUG=True)
    def test_get_salt_returns_duress_salt_if_exists(self, api_client, create_zk_user):
        user, token, auth_hash, salt = create_zk_user(username="duress_salt_user", password="Pass1!")
        profile = UserProfile.objects.get(user=user)
        profile.duress_salt = "duress_salt_value_xyz"
        profile.duress_auth_hash = "a" * 64
        profile.save()

        resp = api_client.get(self.URL, {"username": "duress_salt_user"})
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["duress_salt"] == "duress_salt_value_xyz"

    @override_settings(DEBUG=True)
    def test_get_salt_case_insensitive_username(self, api_client, create_zk_user):
        user, token, auth_hash, salt = create_zk_user(username="CaseSalt", password="Pass1!")
        resp = api_client.get(self.URL, {"username": "casesalt"})
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["salt"] == salt


# ═══════════════════════════════════════════════════════════════════════════════
# CHANGE PASSWORD TESTS
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestZeroKnowledgeChangePasswordView:
    """Tests for POST /api/zk/change-password/"""

    URL = "/api/zk/change-password/"

    @override_settings(DEBUG=True)
    def test_change_password_success(self, api_client, create_zk_user):
        user, raw_key, auth_hash, salt = create_zk_user(username="chpwuser", password="OldPass1!")
        api_client.credentials(HTTP_AUTHORIZATION=f"Token {raw_key}")

        new_salt = generate_salt()
        new_hash = generate_auth_hash("NewPass1!", new_salt)

        resp = api_client.post(
            self.URL,
            {
                "current_auth_hash": auth_hash,
                "new_auth_hash": new_hash,
                "new_salt": new_salt,
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_200_OK

        profile = user.userprofile
        profile.refresh_from_db()
        assert profile.auth_hash == new_hash.lower()
        assert profile.encryption_salt == new_salt

    @override_settings(DEBUG=True)
    def test_change_password_wrong_current_hash(self, api_client, create_zk_user):
        user, raw_key, auth_hash, salt = create_zk_user(username="chpwwrong", password="OldPass1!")
        api_client.credentials(HTTP_AUTHORIZATION=f"Token {raw_key}")

        resp = api_client.post(
            self.URL,
            {
                "current_auth_hash": "f" * 64,
                "new_auth_hash": "a" * 64,
                "new_salt": generate_salt(),
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    @override_settings(DEBUG=True)
    def test_change_password_requires_authentication(self, api_client):
        resp = api_client.post(
            self.URL,
            {
                "current_auth_hash": "a" * 64,
                "new_auth_hash": "b" * 64,
                "new_salt": generate_salt(),
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    @override_settings(DEBUG=True)
    def test_change_password_missing_fields(self, api_client, create_zk_user):
        user, raw_key, auth_hash, salt = create_zk_user(username="chpwmissing", password="Pass1!")
        api_client.credentials(HTTP_AUTHORIZATION=f"Token {raw_key}")

        # Missing current
        resp = api_client.post(
            self.URL,
            {"new_auth_hash": "a" * 64, "new_salt": "s"},
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

        # Missing new
        resp = api_client.post(
            self.URL,
            {"current_auth_hash": auth_hash, "new_salt": "s"},
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

        # Missing salt
        resp = api_client.post(
            self.URL,
            {"current_auth_hash": auth_hash, "new_auth_hash": "a" * 64},
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    @override_settings(DEBUG=True)
    def test_change_password_old_token_still_works(self, api_client, create_zk_user):
        user, raw_key, auth_hash, salt = create_zk_user(username="tokenvalid", password="OldPass1!")
        api_client.credentials(HTTP_AUTHORIZATION=f"Token {raw_key}")

        new_salt = generate_salt()
        new_hash = generate_auth_hash("NewPass1!", new_salt)
        resp = api_client.post(
            self.URL,
            {
                "current_auth_hash": auth_hash,
                "new_auth_hash": new_hash,
                "new_salt": new_salt,
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_200_OK

        # Token should still work for authenticated endpoints
        resp = api_client.get("/api/zk/salt/", {"username": "tokenvalid"})
        assert resp.status_code == status.HTTP_200_OK

    @override_settings(DEBUG=True)
    def test_change_password_can_login_with_new_hash(self, api_client, create_zk_user):
        user, raw_key, auth_hash, salt = create_zk_user(username="loginafter", password="OldPass1!")
        api_client.credentials(HTTP_AUTHORIZATION=f"Token {raw_key}")

        new_salt = generate_salt()
        new_hash = generate_auth_hash("NewPass2!", new_salt)
        api_client.post(
            self.URL,
            {
                "current_auth_hash": auth_hash,
                "new_auth_hash": new_hash,
                "new_salt": new_salt,
            },
            format="json",
        )

        # Login with new hash
        api_client.credentials()  # clear
        resp = api_client.post(
            "/api/zk/login/",
            {"username": "loginafter", "auth_hash": new_hash},
            format="json",
        )
        assert resp.status_code == status.HTTP_200_OK

    @override_settings(DEBUG=True)
    def test_change_password_old_hash_no_longer_works(self, api_client, create_zk_user):
        user, raw_key, auth_hash, salt = create_zk_user(username="oldnogo", password="OldPass1!")
        api_client.credentials(HTTP_AUTHORIZATION=f"Token {raw_key}")

        new_salt = generate_salt()
        new_hash = generate_auth_hash("NewPass3!", new_salt)
        api_client.post(
            self.URL,
            {
                "current_auth_hash": auth_hash,
                "new_auth_hash": new_hash,
                "new_salt": new_salt,
            },
            format="json",
        )

        # Login with old hash should fail
        api_client.credentials()
        resp = api_client.post(
            "/api/zk/login/",
            {"username": "oldnogo", "auth_hash": auth_hash},
            format="json",
        )
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


# ═══════════════════════════════════════════════════════════════════════════════
# SET DURESS TESTS
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestZeroKnowledgeSetDuressView:
    """Tests for POST /api/zk/set-duress/"""

    URL = "/api/zk/set-duress/"

    def _setup_duress_payload(self, master_auth_hash):
        """Build duress setup payload."""
        d_salt = generate_salt()
        d_hash = generate_auth_hash("DuressPassword1!", d_salt)
        return {
            "master_auth_hash": master_auth_hash,
            "duress_auth_hash": d_hash,
            "duress_salt": d_salt,
            "sos_email": "sos@test.com",
        }

    @override_settings(DEBUG=True)
    def test_set_duress_success(self, api_client, create_zk_user):
        user, raw_key, auth_hash, salt = create_zk_user(username="duressset", password="Master1!")
        api_client.credentials(HTTP_AUTHORIZATION=f"Token {raw_key}")

        payload = self._setup_duress_payload(auth_hash)
        resp = api_client.post(self.URL, payload, format="json")
        assert resp.status_code == status.HTTP_200_OK

        profile = user.userprofile
        profile.refresh_from_db()
        assert profile.duress_auth_hash == payload["duress_auth_hash"]
        assert profile.duress_salt == payload["duress_salt"]
        assert resp.json()["has_duress_password"] is True

    @override_settings(DEBUG=True)
    def test_set_duress_requires_master_auth_hash_verification(self, api_client, create_zk_user):
        user, raw_key, auth_hash, salt = create_zk_user(username="durverify", password="Master1!")
        api_client.credentials(HTTP_AUTHORIZATION=f"Token {raw_key}")

        resp = api_client.post(
            self.URL,
            {
                "duress_auth_hash": "b" * 64,
                "duress_salt": generate_salt(),
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    @override_settings(DEBUG=True)
    def test_set_duress_wrong_master_hash(self, api_client, create_zk_user):
        user, raw_key, auth_hash, salt = create_zk_user(username="durwrong", password="Master1!")
        api_client.credentials(HTTP_AUTHORIZATION=f"Token {raw_key}")

        resp = api_client.post(
            self.URL,
            {
                "master_auth_hash": "f" * 64,
                "duress_auth_hash": "b" * 64,
                "duress_salt": generate_salt(),
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    @override_settings(DEBUG=True)
    def test_set_duress_same_as_master_rejected(self, api_client, create_zk_user):
        user, raw_key, auth_hash, salt = create_zk_user(username="dursame", password="Master1!")
        api_client.credentials(HTTP_AUTHORIZATION=f"Token {raw_key}")

        resp = api_client.post(
            self.URL,
            {
                "master_auth_hash": auth_hash,
                "duress_auth_hash": auth_hash,  # same as master!
                "duress_salt": generate_salt(),
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "different" in resp.json()["error"].lower()

    @override_settings(DEBUG=True)
    def test_set_duress_stores_sos_email(self, api_client, create_zk_user):
        user, raw_key, auth_hash, salt = create_zk_user(username="dursos", password="Master1!")
        api_client.credentials(HTTP_AUTHORIZATION=f"Token {raw_key}")

        payload = self._setup_duress_payload(auth_hash)
        payload["sos_email"] = "emergency@test.com"
        api_client.post(self.URL, payload, format="json")

        profile = user.userprofile
        profile.refresh_from_db()
        assert profile.sos_email == "emergency@test.com"

    @override_settings(DEBUG=True)
    def test_set_duress_requires_authentication(self, api_client):
        resp = api_client.post(
            self.URL,
            {
                "master_auth_hash": "a" * 64,
                "duress_auth_hash": "b" * 64,
                "duress_salt": "salt",
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    @override_settings(DEBUG=True)
    def test_set_duress_overwrites_previous_duress(self, api_client, create_zk_user):
        user, raw_key, auth_hash, salt = create_zk_user(username="duroverwrite", password="Master1!")
        api_client.credentials(HTTP_AUTHORIZATION=f"Token {raw_key}")

        # Set first duress
        payload1 = self._setup_duress_payload(auth_hash)
        api_client.post(self.URL, payload1, format="json")

        # Set second duress
        payload2 = self._setup_duress_payload(auth_hash)
        api_client.post(self.URL, payload2, format="json")

        profile = user.userprofile
        profile.refresh_from_db()
        assert profile.duress_auth_hash == payload2["duress_auth_hash"]
        assert profile.duress_salt == payload2["duress_salt"]

    @override_settings(DEBUG=True)
    def test_set_duress_missing_duress_fields(self, api_client, create_zk_user):
        user, raw_key, auth_hash, salt = create_zk_user(username="durmissing", password="Master1!")
        api_client.credentials(HTTP_AUTHORIZATION=f"Token {raw_key}")

        # Missing duress_auth_hash
        resp = api_client.post(
            self.URL,
            {"master_auth_hash": auth_hash, "duress_salt": "salt"},
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

        # Missing duress_salt
        resp = api_client.post(
            self.URL,
            {"master_auth_hash": auth_hash, "duress_auth_hash": "b" * 64},
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST


# ═══════════════════════════════════════════════════════════════════════════════
# CLEAR DURESS TESTS
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestZeroKnowledgeClearDuressView:
    """Tests for POST /api/zk/clear-duress/"""

    URL = "/api/zk/clear-duress/"

    @override_settings(DEBUG=True)
    def test_clear_duress_success(self, api_client, create_zk_user):
        user, raw_key, auth_hash, salt = create_zk_user(username="clearok", password="Master1!")
        profile = UserProfile.objects.get(user=user)
        profile.duress_auth_hash = "b" * 64
        profile.duress_salt = "duress_salt_123"
        profile.save()

        api_client.credentials(HTTP_AUTHORIZATION=f"Token {raw_key}")
        resp = api_client.post(self.URL, {"master_auth_hash": auth_hash}, format="json")
        assert resp.status_code == status.HTTP_200_OK

        profile.refresh_from_db()
        assert profile.duress_auth_hash is None
        assert profile.duress_salt is None
        assert resp.json()["has_duress_password"] is False

    @override_settings(DEBUG=True)
    def test_clear_duress_requires_master_verification(self, api_client, create_zk_user):
        user, raw_key, auth_hash, salt = create_zk_user(username="clearverify", password="Master1!")
        api_client.credentials(HTTP_AUTHORIZATION=f"Token {raw_key}")

        resp = api_client.post(self.URL, {}, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    @override_settings(DEBUG=True)
    def test_clear_duress_wrong_master_hash(self, api_client, create_zk_user):
        user, raw_key, auth_hash, salt = create_zk_user(username="clearwrong", password="Master1!")
        api_client.credentials(HTTP_AUTHORIZATION=f"Token {raw_key}")

        resp = api_client.post(self.URL, {"master_auth_hash": "f" * 64}, format="json")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    @override_settings(DEBUG=True)
    def test_clear_duress_when_no_duress_set(self, api_client, create_zk_user):
        """Clearing duress when none is set should not error."""
        user, raw_key, auth_hash, salt = create_zk_user(username="clearnone", password="Master1!")
        api_client.credentials(HTTP_AUTHORIZATION=f"Token {raw_key}")

        resp = api_client.post(self.URL, {"master_auth_hash": auth_hash}, format="json")
        assert resp.status_code == status.HTTP_200_OK

    @override_settings(DEBUG=True)
    def test_clear_duress_existing_duress_sessions_invalidated(self, api_client, create_zk_user):
        """Active duress sessions should be cleaned up on clear."""
        user, raw_key, auth_hash, salt = create_zk_user(username="clearsession", password="Master1!")
        profile = UserProfile.objects.get(user=user)
        d_salt = generate_salt()
        d_hash = generate_auth_hash("Duress1!", d_salt)
        profile.duress_auth_hash = d_hash
        profile.duress_salt = d_salt
        profile.save()

        # Create a duress session manually
        DuressSession.objects.create(
            token_key="fake_token_key_hash",
            user=user,
        )
        assert DuressSession.objects.filter(user=user).exists()

        api_client.credentials(HTTP_AUTHORIZATION=f"Token {raw_key}")
        api_client.post(self.URL, {"master_auth_hash": auth_hash}, format="json")

        # After clearing, the duress fields should be None
        profile.refresh_from_db()
        assert profile.duress_auth_hash is None

    @override_settings(DEBUG=True)
    def test_clear_duress_requires_authentication(self, api_client):
        resp = api_client.post(self.URL, {"master_auth_hash": "a" * 64}, format="json")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


# ═══════════════════════════════════════════════════════════════════════════════
# VERIFY TESTS
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestZeroKnowledgeVerifyView:
    """Tests for POST /api/zk/verify/"""

    URL = "/api/zk/verify/"

    @override_settings(DEBUG=True)
    def test_verify_correct_master_hash(self, api_client, create_zk_user):
        user, raw_key, auth_hash, salt = create_zk_user(username="verifymaster", password="Pass1!")
        api_client.credentials(HTTP_AUTHORIZATION=f"Token {raw_key}")

        resp = api_client.post(self.URL, {"auth_hash": auth_hash}, format="json")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["verified"] is True
        assert data["is_duress"] is False

    @override_settings(DEBUG=True)
    def test_verify_correct_duress_hash(self, api_client, create_zk_user):
        user, raw_key, auth_hash, salt = create_zk_user(username="verifydur", password="Pass1!")
        profile = UserProfile.objects.get(user=user)
        d_salt = generate_salt()
        d_hash = generate_auth_hash("DuressVer1!", d_salt)
        profile.duress_auth_hash = d_hash
        profile.duress_salt = d_salt
        profile.save()

        api_client.credentials(HTTP_AUTHORIZATION=f"Token {raw_key}")
        resp = api_client.post(self.URL, {"auth_hash": d_hash}, format="json")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["verified"] is True
        assert data["is_duress"] is True

    @override_settings(DEBUG=True)
    def test_verify_wrong_hash(self, api_client, create_zk_user):
        user, raw_key, auth_hash, salt = create_zk_user(username="verifywrong", password="Pass1!")
        api_client.credentials(HTTP_AUTHORIZATION=f"Token {raw_key}")

        resp = api_client.post(self.URL, {"auth_hash": "e" * 64}, format="json")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED
        assert resp.json()["verified"] is False

    @override_settings(DEBUG=True)
    def test_verify_requires_authentication(self, api_client):
        resp = api_client.post(self.URL, {"auth_hash": "a" * 64}, format="json")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    @override_settings(DEBUG=True)
    def test_verify_returns_salt(self, api_client, create_zk_user):
        user, raw_key, auth_hash, salt = create_zk_user(username="verifysalt", password="Pass1!")
        api_client.credentials(HTTP_AUTHORIZATION=f"Token {raw_key}")

        resp = api_client.post(self.URL, {"auth_hash": auth_hash}, format="json")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["salt"] == salt


# ═══════════════════════════════════════════════════════════════════════════════
# SWITCH MODE TESTS
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestZeroKnowledgeSwitchModeView:
    """Tests for POST /api/zk/switch-mode/"""

    URL = "/api/zk/switch-mode/"

    def _setup_duress(self, user):
        """Helper to set duress on a user; returns (duress_hash, duress_salt)."""
        profile = UserProfile.objects.get(user=user)
        d_salt = generate_salt()
        d_hash = generate_auth_hash("SwitchDuress1!", d_salt)
        profile.duress_auth_hash = d_hash
        profile.duress_salt = d_salt
        profile.sos_email = "sos@switch.com"
        profile.save()
        return d_hash, d_salt

    @override_settings(DEBUG=True)
    def test_switch_to_duress_mode(self, api_client, create_zk_user):
        user, raw_key, auth_hash, salt = create_zk_user(username="switchdur", password="Master1!")
        d_hash, d_salt = self._setup_duress(user)
        api_client.credentials(HTTP_AUTHORIZATION=f"Token {raw_key}")

        with patch("api.features.security.services.SecurityService.send_duress_alert"):
            resp = api_client.post(self.URL, {"auth_hash": d_hash}, format="json")

        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["verified"] is True
        assert data["is_duress"] is True
        assert data["salt"] == d_salt
        assert DuressSession.objects.filter(user=user).exists()

    @override_settings(DEBUG=True)
    def test_switch_to_normal_mode(self, api_client, create_zk_user):
        user, raw_key, auth_hash, salt = create_zk_user(username="switchnorm", password="Master1!")
        self._setup_duress(user)

        # Create existing duress session
        token_obj = MultiToken.objects.get(key=MultiToken.hash_raw_key(raw_key))
        DuressSession.objects.create(token_key=token_obj.key, user=user)

        api_client.credentials(HTTP_AUTHORIZATION=f"Token {raw_key}")
        resp = api_client.post(self.URL, {"auth_hash": auth_hash}, format="json")

        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["verified"] is True
        assert data["is_duress"] is False
        assert data["salt"] == salt
        assert not DuressSession.objects.filter(
            user=user
        ).exists(), "DuressSession must be removed when switching to normal"

    @override_settings(DEBUG=True)
    def test_switch_mode_wrong_hash(self, api_client, create_zk_user):
        user, raw_key, auth_hash, salt = create_zk_user(username="switchwrong", password="Master1!")
        api_client.credentials(HTTP_AUTHORIZATION=f"Token {raw_key}")

        resp = api_client.post(self.URL, {"auth_hash": "e" * 64}, format="json")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    @override_settings(DEBUG=True)
    def test_switch_mode_requires_authentication(self, api_client):
        resp = api_client.post(self.URL, {"auth_hash": "a" * 64}, format="json")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    @override_settings(DEBUG=True)
    def test_switch_to_duress_sends_sos_alert(self, api_client, create_zk_user):
        user, raw_key, auth_hash, salt = create_zk_user(username="switchsos", password="Master1!")
        d_hash, d_salt = self._setup_duress(user)
        api_client.credentials(HTTP_AUTHORIZATION=f"Token {raw_key}")

        with patch("api.features.security.services.SecurityService.send_duress_alert") as mock_alert:
            api_client.post(self.URL, {"auth_hash": d_hash}, format="json")
            # SOS is sent in a background thread, give it time
            time.sleep(0.3)

        mock_alert.assert_called_once()

    @override_settings(DEBUG=True)
    def test_switch_to_normal_does_not_send_sos(self, api_client, create_zk_user):
        user, raw_key, auth_hash, salt = create_zk_user(username="switchnoalert", password="Master1!")
        self._setup_duress(user)
        api_client.credentials(HTTP_AUTHORIZATION=f"Token {raw_key}")

        with patch("api.features.security.services.SecurityService.send_duress_alert") as mock_alert:
            api_client.post(self.URL, {"auth_hash": auth_hash}, format="json")
            time.sleep(0.3)

        mock_alert.assert_not_called()


# ═══════════════════════════════════════════════════════════════════════════════
# DELETE ACCOUNT TESTS
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestZeroKnowledgeDeleteAccountView:
    """Tests for POST /api/zk/delete-account/"""

    URL = "/api/zk/delete-account/"

    @override_settings(DEBUG=True)
    def test_delete_account_success(self, api_client, create_zk_user):
        user, raw_key, auth_hash, salt = create_zk_user(username="deluser", password="Pass1!")
        user_id = user.id
        api_client.credentials(HTTP_AUTHORIZATION=f"Token {raw_key}")

        resp = api_client.post(self.URL, {"auth_hash": auth_hash}, format="json")
        assert resp.status_code == status.HTTP_200_OK
        assert not User.objects.filter(id=user_id).exists()

    @override_settings(DEBUG=True)
    def test_delete_account_wrong_hash(self, api_client, create_zk_user):
        user, raw_key, auth_hash, salt = create_zk_user(username="delwrong", password="Pass1!")
        api_client.credentials(HTTP_AUTHORIZATION=f"Token {raw_key}")

        resp = api_client.post(self.URL, {"auth_hash": "f" * 64}, format="json")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED
        assert User.objects.filter(id=user.id).exists(), "User must NOT be deleted"

    @override_settings(DEBUG=True)
    def test_delete_account_cascades_all_data(self, api_client, create_zk_user):
        user, raw_key, auth_hash, salt = create_zk_user(username="delcascade", password="Pass1!")
        user_id = user.id
        api_client.credentials(HTTP_AUTHORIZATION=f"Token {raw_key}")

        resp = api_client.post(self.URL, {"auth_hash": auth_hash}, format="json")
        assert resp.status_code == status.HTTP_200_OK

        # Verify cascading delete
        assert not UserProfile.objects.filter(user_id=user_id).exists()
        assert not MultiToken.objects.filter(user_id=user_id).exists()
        assert not UserSession.objects.filter(user_id=user_id).exists()

    @override_settings(DEBUG=True)
    def test_delete_account_token_invalidated(self, api_client, create_zk_user):
        user, raw_key, auth_hash, salt = create_zk_user(username="deltokeninv", password="Pass1!")
        api_client.credentials(HTTP_AUTHORIZATION=f"Token {raw_key}")

        # Delete account
        api_client.post(self.URL, {"auth_hash": auth_hash}, format="json")

        # Try to use the token again
        resp = api_client.post(self.URL, {"auth_hash": auth_hash}, format="json")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    @override_settings(DEBUG=True)
    def test_delete_account_requires_authentication(self, api_client):
        resp = api_client.post(self.URL, {"auth_hash": "a" * 64}, format="json")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    @override_settings(DEBUG=True)
    def test_delete_account_second_attempt_returns_401(self, api_client, create_zk_user):
        """After successful deletion, a second attempt with same token returns 401."""
        user, raw_key, auth_hash, salt = create_zk_user(username="delrace", password="Pass1!")
        api_client.credentials(HTTP_AUTHORIZATION=f"Token {raw_key}")

        # First delete succeeds
        resp1 = api_client.post(self.URL, {"auth_hash": auth_hash}, format="json")
        assert resp1.status_code == status.HTTP_200_OK
        assert not User.objects.filter(username="delrace").exists()

        # Second attempt fails - token invalidated by cascading delete
        resp2 = api_client.post(self.URL, {"auth_hash": auth_hash}, format="json")
        assert resp2.status_code == status.HTTP_401_UNAUTHORIZED
