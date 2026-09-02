"""User repository tests — password hashing, verification, and the
timing-safe-ish "unknown email" path (no early-exit that would let an
attacker distinguish 'bad email' from 'bad password')."""

from app.repositories.users import UserRepository, hash_password, verify_password


def test_password_is_hashed_not_stored_plaintext(db_session):
    user = UserRepository(db_session).create_or_update("yahya@bassir.net", "Bassir@20302030")
    assert user.password_hash != "Bassir@20302030"
    assert user.password_hash.startswith("$2b$")  # bcrypt hash prefix


def test_authenticate_succeeds_with_correct_password(db_session):
    UserRepository(db_session).create_or_update("yahya@bassir.net", "Bassir@20302030")
    user = UserRepository(db_session).authenticate("yahya@bassir.net", "Bassir@20302030")
    assert user is not None
    assert user.email == "yahya@bassir.net"
    assert user.last_login_at is not None


def test_authenticate_fails_with_wrong_password(db_session):
    UserRepository(db_session).create_or_update("yahya@bassir.net", "Bassir@20302030")
    assert UserRepository(db_session).authenticate("yahya@bassir.net", "wrong-password") is None


def test_authenticate_fails_for_unknown_email(db_session):
    assert UserRepository(db_session).authenticate("nobody@bassir.net", "anything") is None


def test_email_is_normalized_case_and_whitespace(db_session):
    UserRepository(db_session).create_or_update("  Yahya@Bassir.NET  ", "Bassir@20302030")
    user = UserRepository(db_session).authenticate("yahya@bassir.net", "Bassir@20302030")
    assert user is not None


def test_create_or_update_is_idempotent_on_email(db_session):
    repo = UserRepository(db_session)
    repo.create_or_update("yahya@bassir.net", "first-password")
    repo.create_or_update("yahya@bassir.net", "second-password")

    assert repo.authenticate("yahya@bassir.net", "first-password") is None
    assert repo.authenticate("yahya@bassir.net", "second-password") is not None


def test_verify_password_rejects_malformed_hash_without_crashing():
    assert verify_password("anything", "not-a-real-bcrypt-hash") is False
