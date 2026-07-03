"""Email notifications (best-effort; console backend by default).

Configure SMTP via env (EMAIL_BACKEND/EMAIL_HOST/...) and the HR inbox
via RETENTION_HR_EMAIL. Failures are logged, never raised.
"""

from __future__ import annotations

import logging
import os

from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


def _send(subject: str, body: str, recipients: list[str]) -> bool:
    recipients = [r for r in recipients if r]
    if not recipients:
        return False
    try:
        send_mail(
            subject,
            body,
            getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@smarthr360.dev"),
            recipients,
            fail_silently=False,
        )
        return True
    except Exception as exc:  # pragma: no cover - notification only
        logger.warning("email notification failed: %s", exc)
        return False


def notify_conversation_opened(employee, conversation) -> bool:
    """Tell the employee the retention assistant wants to talk."""
    return _send(
        "[SmartHR360] Votre assistant RH souhaite échanger avec vous",
        (
            f"Bonjour {employee.name},\n\n"
            f"{conversation.messages[-1]['content']}\n\n"
            "Répondez depuis votre espace SmartHR360.\n\n"
            "Cette conversation est confidentielle mais son résultat "
            "(votre besoin principal) sera partagé avec les RH. "
            "Vous pouvez y mettre fin à tout moment."
        ),
        [employee.email],
    )


def notify_action_pending(action) -> bool:
    """Tell the HR inbox a retention action awaits review."""
    hr_inbox = os.environ.get("RETENTION_HR_EMAIL", "")
    return _send(
        f"[SmartHR360] Retention action pending review ({action.priority.upper()})",
        (
            f"Employee: {action.employee.name} ({action.employee.employee_id})\n"
            f"Identified need: {action.conversation.identified_need}\n"
            f"Proposed action: {action.description}\n\n"
            "Review it in SmartHR360: /api/retention/actions/"
        ),
        [hr_inbox],
    )
