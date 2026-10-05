"""
Tests for the PGP-encrypted/signed submission e-mail notifications.

Covers the ``ALLOW_EMAILS`` safety gate, the GnuPG sign+encrypt helper, and the
``notify_submission`` hook (student confirmation + assistant notification) in
:mod:`config.services.notifications`.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from config.factory import AppSettingsFactory, AssistantCourseFactory, CourseFactory
from config.services import notifications
from config.services.notifications import (
    emails_enabled,
    gpg_sign_and_encrypt,
    notify_submission,
    send,
)
from django.test import override_settings
from users.factory import AssistantUserFactory, UserFactory

if TYPE_CHECKING:  # pragma: no cover
    from config.models import AppSettings

GPG_BIN = shutil.which("gpg")

needs_gpg = pytest.mark.skipif(GPG_BIN is None, reason="gpg binary not available")

pytestmark = pytest.mark.django_db


def _run_gpg(home: str, *args: str) -> subprocess.CompletedProcess[bytes]:
    """Run the ``gpg`` binary inside ``home`` (full path to satisfy the linter)."""
    env = dict(os.environ, GNUPGHOME=home)
    return subprocess.run([GPG_BIN, *args], env=env, capture_output=True, check=False)  # noqa: S603


def _generate_keypair() -> tuple[str, str]:
    """Generate an (unprotected) RSA-1024 key and return (public, private) blocks."""
    import gnupg

    params = (
        "%no-protection\n"
        "Key-Type: RSA\n"
        "Key-Length: 1024\n"
        "Name-Real: Test\n"
        "Name-Email: test@flamecheck.local\n"
        "Expire-Date: 0\n"
        "%commit\n"
    )
    home = tempfile.mkdtemp(prefix="fc-test-gpg-")
    try:
        env = dict(os.environ, GNUPGHOME=home)
        subprocess.run(  # noqa: S603
            [GPG_BIN, "--batch", "--gen-key", "-"],
            input=params.encode(),
            env=env,
            capture_output=True,
            check=True,
        )
        gpg = gnupg.GPG(gnupghome=home)
        fingerprint = gpg.list_keys()[0]["fingerprint"]
        public = gpg.export_keys(fingerprint)
        private = gpg.export_keys(fingerprint, secret=True, passphrase=b"")
        return public, private
    finally:
        shutil.rmtree(home, ignore_errors=True)


# ---------------------------------------------------------------------------
# ALLOW_EMAILS gate
# ---------------------------------------------------------------------------
class TestEmailsEnabledGate:
    """The ``ALLOW_EMAILS`` master switch (env / settings)."""

    def test_disabled_by_default(self) -> None:
        assert emails_enabled() is False

    def test_enabled_when_setting_truthy(self) -> None:
        with override_settings(ALLOW_EMAILS=True):
            assert emails_enabled() is True

    def test_send_is_a_noop_when_disabled(self) -> None:
        settings = AppSettingsFactory(smtp_host="smtp.example.org")
        with override_settings(ALLOW_EMAILS=False):
            assert send(settings, to="a@example.org", subject="s", body="b") is False


# ---------------------------------------------------------------------------
# GnuPG sign + encrypt helper
# ---------------------------------------------------------------------------
@needs_gpg
class TestGpgSignAndEncrypt:
    def test_roundtrip_signs_and_encrypts(self) -> None:
        public, private = _generate_keypair()
        block = gpg_sign_and_encrypt("secret body", public_key=public, private_key=private, passphrase="")
        assert block.startswith("-----BEGIN PGP MESSAGE-----")

        # The recipient (holder of the private key) can decrypt and verify the
        # signature (GOODSIG) — proving the message is both encrypted and signed.
        import gnupg

        home = tempfile.mkdtemp(prefix="fc-verify-gpg-")
        try:
            gpg = gnupg.GPG(gnupghome=home)
            gpg.import_keys(public)
            gpg.import_keys(private)
            msg_path = os.path.join(home, "msg.pgp")
            with open(msg_path, "w", encoding="utf-8") as fh:
                fh.write(block)
            result = _run_gpg(home, "--batch", "--pinentry-mode", "loopback", "--decrypt", "--status-fd", "2", msg_path)
            assert result.stdout.decode().strip() == "secret body"
            status = result.stderr.decode(errors="ignore")
            assert "GOODSIG" in status
            assert "DECRYPTION_OKAY" in status
        finally:
            shutil.rmtree(home, ignore_errors=True)

    def test_missing_public_key_raises(self) -> None:
        with pytest.raises(ValueError):
            gpg_sign_and_encrypt("b", public_key="", private_key="x", passphrase="")

    def test_missing_private_key_raises(self) -> None:
        with pytest.raises(ValueError):
            gpg_sign_and_encrypt("b", public_key="x", private_key="", passphrase="")


# ---------------------------------------------------------------------------
# notify_submission hook
# ---------------------------------------------------------------------------
class _FakeSMTP:
    """A stand-in for :class:`smtplib.SMTP` capturing sent messages."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, object]] = []

    def login(self, *args: object) -> None:
        pass

    def starttls(self) -> None:
        pass

    def send_message(self, message: object) -> None:
        self.sent.append((str(message["To"]), message))

    def quit(self) -> None:
        pass


def _settings_with_keys() -> AppSettings:
    """
    An AppSettings row with (non-empty) PGP keys + SMTP host so a send is attempted.

    The key values are dummies on purpose: the notification tests mock
    :func:`gpg_sign_and_encrypt`, so the keys only need to be non-empty to pass
    the "is a key configured?" checks.
    """
    return AppSettingsFactory(
        smtp_host="smtp.example.org",
        smtp_port=587,
        smtp_from_email="flamecheck@example.org",
        pgp_public_key="-----BEGIN PGP PUBLIC KEY BLOCK-----\ndummy\n-----END PGP PUBLIC KEY BLOCK-----",
        pgp_private_key="-----BEGIN PGP PRIVATE KEY BLOCK-----\ndummy\n-----END PGP PRIVATE KEY BLOCK-----",
        pgp_private_key_passphrase="",
    )


class TestNotifySubmission:
    def _course(self, notify_student: bool):
        course = CourseFactory(notify_student_on_submission=notify_student)
        student = UserFactory(email="student@example.org", first_name="Lena", last_name="May")
        assistant = AssistantUserFactory(email="assistant@example.org", first_name="Max", last_name="Berg")
        AssistantCourseFactory(assistant=assistant, course=course)
        return course, student, assistant

    def test_noop_when_gate_disabled(self) -> None:
        course, student, _assistant = self._course(notify_student=True)
        AppSettingsFactory(notify_assistant_on_submission=True, smtp_host="smtp.example.org")
        with override_settings(ALLOW_EMAILS=False):
            with patch.object(notifications, "_connect") as connect:
                notify_submission(
                    course=course,
                    student=student,
                    analysis_name="Analysis 1",
                    score=8,
                    ideal_score=10,
                    submission_number=1,
                )
                connect.assert_not_called()

    def test_student_confirmation_sent(self) -> None:
        course, student, _assistant = self._course(notify_student=True)
        settings = _settings_with_keys()
        settings.notify_assistant_on_submission = False
        settings.save()
        fake = _FakeSMTP()
        with override_settings(ALLOW_EMAILS=True):
            with (
                patch.object(notifications, "_connect", return_value=fake),
                patch.object(
                    notifications,
                    "gpg_sign_and_encrypt",
                    return_value="-----BEGIN PGP MESSAGE-----\nX\n-----END PGP MESSAGE-----",
                ),
            ):
                notify_submission(
                    course=course,
                    student=student,
                    analysis_name="Analysis 1",
                    score=8,
                    ideal_score=10,
                    submission_number=1,
                )
        recipients = [to for to, _ in fake.sent]
        assert "student@example.org" in recipients
        assert "assistant@example.org" not in recipients  # global switch off
        subject = str(fake.sent[0][1]["Subject"])
        assert "Analysis 1" in subject

    def test_assistant_notification_sent(self) -> None:
        course, student, _assistant = self._course(notify_student=False)
        settings = _settings_with_keys()
        settings.notify_assistant_on_submission = True
        settings.save()
        fake = _FakeSMTP()
        with override_settings(ALLOW_EMAILS=True):
            with (
                patch.object(notifications, "_connect", return_value=fake),
                patch.object(
                    notifications,
                    "gpg_sign_and_encrypt",
                    return_value="-----BEGIN PGP MESSAGE-----\nX\n-----END PGP MESSAGE-----",
                ),
            ):
                notify_submission(
                    course=course,
                    student=student,
                    analysis_name="Analysis 1",
                    score=10,
                    ideal_score=10,
                    submission_number=2,
                    submission_kind="mc",
                )
        recipients = [to for to, _ in fake.sent]
        assert "assistant@example.org" in recipients
        assert "student@example.org" not in recipients  # course switch off

    def test_both_switches_send_to_both(self) -> None:
        course, student, _assistant = self._course(notify_student=True)
        settings = _settings_with_keys()
        settings.notify_assistant_on_submission = True
        settings.save()
        fake = _FakeSMTP()
        with override_settings(ALLOW_EMAILS=True):
            with (
                patch.object(notifications, "_connect", return_value=fake),
                patch.object(
                    notifications,
                    "gpg_sign_and_encrypt",
                    return_value="-----BEGIN PGP MESSAGE-----\nX\n-----END PGP MESSAGE-----",
                ),
            ):
                notify_submission(
                    course=course,
                    student=student,
                    analysis_name="Analysis 1",
                    score=6,
                    ideal_score=10,
                    submission_number=1,
                )
        recipients = [to for to, _ in fake.sent]
        assert "student@example.org" in recipients
        assert "assistant@example.org" in recipients
        assert len(fake.sent) == 2

    def test_never_raises_on_missing_email(self) -> None:
        course = CourseFactory(notify_student_on_submission=True)
        student = UserFactory(email="")  # no e-mail address
        AppSettingsFactory(notify_assistant_on_submission=False, smtp_host="smtp.example.org")
        fake = _FakeSMTP()
        with override_settings(ALLOW_EMAILS=True):
            with patch.object(notifications, "_connect", return_value=fake):
                notify_submission(
                    course=course,
                    student=student,
                    analysis_name="Analysis 1",
                    score=10,
                    ideal_score=10,
                    submission_number=1,
                )
        # Student has no e-mail and the assistant switch is off, so nothing is sent.
        assert fake.sent == []
