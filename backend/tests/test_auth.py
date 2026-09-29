from uuid import uuid4

import jwt
import pytest

from backend.core.auth import create_access_token, decode_access_token, hash_password, verify_password
from backend.core.users import LastAdminError, SelfActionError, guard_last_admin, guard_not_self


def test_hash_and_verify_password_round_trip():
    hashed = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", hashed) is True


def test_verify_password_rejects_wrong_password():
    hashed = hash_password("correct horse battery staple")
    assert verify_password("wrong password", hashed) is False


def test_access_token_round_trip():
    user_id = uuid4()
    token = create_access_token(user_id)
    assert decode_access_token(token) == user_id


def test_access_token_rejects_expired_token(monkeypatch):
    from backend.core import auth as auth_module

    settings = auth_module.get_settings()
    monkeypatch.setattr(settings, "jwt_expires_minutes", -1)  # already expired
    token = create_access_token(uuid4())
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(token)


def test_access_token_rejects_bad_signature():
    token = create_access_token(uuid4())
    # change several characters - changing only the last one can decode to the same bytes
    tampered = token[:-10] + ("A" * 10 if not token.endswith("A" * 10) else "B" * 10)
    with pytest.raises(jwt.PyJWTError):
        decode_access_token(tampered)


def test_guard_not_self_allows_other_user():
    guard_not_self(uuid4(), uuid4())  # no error


def test_guard_not_self_blocks_own_account():
    same_id = uuid4()
    with pytest.raises(SelfActionError):
        guard_not_self(same_id, same_id)


def test_guard_last_admin_allows_when_another_admin_exists():
    guard_last_admin(is_currently_active_admin=True, other_active_admins_count=1)  # no error


def test_guard_last_admin_allows_when_target_is_not_currently_an_active_admin():
    guard_last_admin(is_currently_active_admin=False, other_active_admins_count=0)  # no error


def test_guard_last_admin_blocks_removing_the_only_admin():
    with pytest.raises(LastAdminError):
        guard_last_admin(is_currently_active_admin=True, other_active_admins_count=0)
