import logging

from .models import ActivityLog

logger = logging.getLogger(__name__)


def log_activity(actor, hotel, action, message, **metadata):
    """Fire-and-forget staff activity record. Never breaks the request."""
    try:
        if hotel is None:
            return
        ActivityLog.objects.create(
            actor=actor, hotel=hotel, action=action, message=message, metadata=metadata
        )
    except Exception:
        logger.exception("activity log failed")
