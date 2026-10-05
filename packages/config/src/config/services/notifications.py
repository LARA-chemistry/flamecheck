"""
E-mail notifications for student submissions (PGP-encrypted + signed).

Two independent in-app switches control whether e-mails are sent:

* the **course** switch ``Course.notify_student_on_submission`` (Admin → Courses)
  sends the *student* a confirmation for every submission in that course, and
* the **global** switch ``AppSettings.notify_assistant_on_submission``
  (Admin → Settings → Notifications) sends the course's *assistants* a
  notification for every submission.

On top of that, **every** send is gated by the ``ALLOW_EMAILS`` environment
variable (exposed as ``settings.ALLOW_EMAILS``, defaulting to ``False``). Unless
that variable is set to a truthy value in the (docker) container, no e-mail is
sent at all — this is the extra safety layer that keeps staging and demo
environments from ever sending e-mail, even when the in-app switches are on.

The message body is signed with the configured PGP *private* key and encrypted
for the configured PGP *public* key (GnuPG via :mod:`gnupg`), so only the
holder of the matching private key can read it, and the recipient can verify the
sender's signature. The armored PGP block is delivered as a plain-text e-mail
body through the configured SMTP server.
"""

from __future__ import annotations

import logging
import smtplib
import tempfile
from email.message import EmailMessage
from typing import TYPE_CHECKING, Any

from django.conf import settings
from django.utils import timezone

from ..models import AppSettings, AssistantCourse, Course

if TYPE_CHECKING:  # pragma: no cover
    from users.models import User

logger = logging.getLogger(__name__)


def emails_enabled() -> bool:
    """
    Return whether e-mail sending is allowed at all (the ``ALLOW_EMAILS`` gate).

    This is the master safety switch: it reads the ``ALLOW_EMAILS`` environment
    variable (via ``settings.ALLOW_EMAILS``) and defaults to ``False``. When it
    is not enabled, no notification e-mail is sent regardless of the in-app
    switches.
    """
    return bool(getattr(settings, "ALLOW_EMAILS", False))


def _primary_fingerprint(keys: list[dict[str, Any]]) -> str | None:
    """Return the first (primary) key's fingerprint, or ``None``."""
    for key in keys:
        fingerprint = key.get("fingerprint")
        if fingerprint and not key.get("revoked"):
            return fingerprint
    return None


def gpg_sign_and_encrypt(body: str, *, public_key: str, private_key: str, passphrase: str = "") -> str:
    """
    Sign ``body`` with the PGP private key and encrypt it for the public key.

    A throw-away GnuPG home directory is used, into which the recipient's public
    key and the signing (private) key are imported, so the host keyring is never
    touched. Returns the armored ``-----BEGIN PGP MESSAGE-----`` block.

    Args:
        body: The plain-text message to protect.
        public_key: Armored public key to encrypt for (the recipient's key).
        private_key: Armored private key to sign with.
        passphrase: Passphrase for the private key (empty when unprotected).

    Raises:
        ValueError: When a key is missing or GnuPG cannot process the message.

    """
    import gnupg  # imported lazily: only needed when actually sending e-mail

    if not public_key or not public_key.strip():
        raise ValueError("A PGP public key is required for encryption.")
    if not private_key or not private_key.strip():
        raise ValueError("A PGP private key is required for signing.")
    # Pass ``None`` (not an empty byte string) when the key is unprotected: gpg
    # only accepts a passphrase argument for a protected key.
    passphrase_bytes = passphrase.encode("utf-8") if passphrase else None

    with tempfile.TemporaryDirectory(prefix="flamecheck-gpg-") as home:
        gpg = gnupg.GPG(gnupghome=home)
        gpg.import_keys(public_key)
        gpg.import_keys(private_key, passphrase=passphrase_bytes)
        encrypt_fingerprint = _primary_fingerprint(gpg.list_keys())
        sign_fingerprint = _primary_fingerprint(gpg.list_keys(secret=True))
        if encrypt_fingerprint is None:
            raise ValueError("Could not find an importable PGP public key.")
        if sign_fingerprint is None:
            raise ValueError("Could not find an importable PGP private key.")
        encrypted = gpg.encrypt(
            recipients=[encrypt_fingerprint],
            data=body.encode("utf-8"),
            sign=sign_fingerprint,
            passphrase=passphrase_bytes,
            always_trust=True,
        )
        if not getattr(encrypted, "ok", False):
            raise ValueError(f"GnuPG failed to build the message: {getattr(encrypted, 'status', 'unknown')}")
        return str(encrypted)


def _connect(settings_row: AppSettings) -> smtplib.SMTP:
    """Open an SMTP connection according to the configured security mode."""
    host = settings_row.smtp_host
    port = int(settings_row.smtp_port or 0)
    if settings_row.smtp_security == AppSettings.SMTPSecurity.SSL:
        return smtplib.SMTP_SSL(host, port, timeout=30)
    server = smtplib.SMTP(host, port, timeout=30)
    if settings_row.smtp_security == AppSettings.SMTPSecurity.TLS:
        server.starttls()
    return server


def send(settings_row: AppSettings, *, to: str, subject: str, body: str) -> bool:
    """
    Build one PGP-encrypted/signed e-mail and send it via the configured SMTP.

    Returns ``True`` when the e-mail was actually handed to the SMTP server and
    ``False`` when it was skipped (``ALLOW_EMAILS`` off, empty recipient, or
    missing PGP / SMTP configuration). Failures are logged and never raised, so
    a broken e-mail setup can never break a student submission.
    """
    if not emails_enabled():
        logger.info("E-mail sending disabled (ALLOW_EMAILS off); skipping to=%r subject=%r", to, subject)
        return False
    if not to:
        logger.warning("Skipping notification e-mail: empty recipient address (subject=%r)", subject)
        return False
    if not settings_row.pgp_public_key or not settings_row.pgp_private_key:
        logger.warning("Skipping notification e-mail: PGP keys not configured (subject=%r)", subject)
        return False
    if not settings_row.smtp_host:
        logger.warning("Skipping notification e-mail: SMTP host not configured (subject=%r)", subject)
        return False

    try:
        pgp_body = gpg_sign_and_encrypt(
            body,
            public_key=settings_row.pgp_public_key,
            private_key=settings_row.pgp_private_key,
            passphrase=settings_row.pgp_private_key_passphrase,
        )
        message = EmailMessage()
        message["From"] = settings_row.smtp_from_email or settings.DEFAULT_FROM_EMAIL
        message["To"] = to
        message["Subject"] = f"{settings.EMAIL_SUBJECT_PREFIX}{subject}"
        message.set_content(
            "The body of this e-mail is PGP-encrypted and signed.\n"
            "Open the block below in a mail client with PGP support\n"
            "(for example Thunderbird with Enigmail, or GPG Mail).\n\n" + pgp_body
        )
        server = _connect(settings_row)
        try:
            if settings_row.smtp_username:
                server.login(settings_row.smtp_username, settings_row.smtp_password)
            server.send_message(message)
        finally:
            server.quit()
    except Exception as exc:
        logger.exception("Failed to send notification e-mail to %r (subject=%r): %s", to, subject, exc)
        return False
    logger.info("Sent notification e-mail to %r (subject=%r)", to, subject)
    return True


def notify_submission(
    *,
    course: Course,
    student: User,
    analysis_name: str,
    score: int | None,
    ideal_score: int | None,
    submission_number: int,
    submission_kind: str = "analysis",
) -> None:
    """
    Send submission-confirmation e-mails for a freshly recorded submission.

    Sends to the student when the course's ``notify_student_on_submission`` is
    set and the student has an e-mail address, and to the course's assistants
    when the global ``notify_assistant_on_submission`` is set. Every send is
    additionally gated by :func:`emails_enabled` (the ``ALLOW_EMAILS``
    environment variable). This function never raises: e-mail problems are
    logged so a submission always succeeds.

    Args:
        course: The course the submission belongs to.
        student: The student who submitted.
        analysis_name: Human-readable name of the analysis / card.
        score: The recorded score (may be ``None``).
        ideal_score: The ideal (maximum) score (may be ``None``).
        submission_number: 1-based ordinal of the submission.
        submission_kind: ``"analysis"`` or ``"mc"`` (affects the wording only).

    """
    try:
        settings_row = AppSettings.get_instance()
        when = timezone.now().strftime("%Y-%m-%d %H:%M")
        kind_text = "multiple-choice card" if submission_kind == "mc" else "analysis"
        score_text = f"{score}/{ideal_score}" if ideal_score is not None else (str(score) if score is not None else "-")
        student_name = getattr(student, "full_name", "") or student.username
        labspace = getattr(student, "labspace_id", "") or ""

        # 1) Student confirmation (per-course switch).
        if course.notify_student_on_submission and getattr(student, "email", ""):
            student_body = (
                f"Your {kind_text} submission has been received and graded.\n\n"
                f"Course: {course.name}\n"
                f"Task: {analysis_name} (attempt #{submission_number})\n"
                f"Score: {score_text}\n"
                f"Submitted at: {when}\n"
            )
            send(settings_row, to=student.email, subject=f"Submission received: {analysis_name}", body=student_body)

        # 2) Assistant notification (global switch).
        if settings_row.notify_assistant_on_submission:
            assistant_body = (
                f"A student submission was recorded.\n\n"
                f"Course: {course.name}\n"
                f"Student: {student_name}" + (f" (labspace {labspace})" if labspace else "") + "\n"
                f"Task: {analysis_name} (attempt #{submission_number})\n"
                f"Score: {score_text}\n"
                f"Submitted at: {when}\n"
            )
            assignments = AssistantCourse.objects.filter(course=course).select_related("assistant")
            for assignment in assignments:
                assistant = assignment.assistant
                if assistant is not None and assistant.email:
                    send(
                        settings_row,
                        to=assistant.email,
                        subject=f"Submission: {student.username} - {analysis_name}",
                        body=assistant_body,
                    )
    except Exception:
        logger.exception("Error while preparing submission notification e-mails")
