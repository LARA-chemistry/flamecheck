"""
Per-app test factories for the ``users`` app.

The canonical factory definitions live in :mod:`users.factory` (one ``factory.py``
per app, per the project convention). This module re-exports them so the
cookiecutter-style per-app tests (``users/tests/``) keep working while there is a
single source of truth for how a ``User`` is built.
"""

from users.factory import (
    AdminUserFactory,
    AssistantUserFactory,
    LoginAttemptFactory,
    StudentAssignmentFactory,
    StudentBarcodeFactory,
    UserFactory,
)

__all__ = [
    "AdminUserFactory",
    "AssistantUserFactory",
    "LoginAttemptFactory",
    "StudentAssignmentFactory",
    "StudentBarcodeFactory",
    "UserFactory",
]
