"""Photon iMessage sender. Owner: Ian. STUB: replace with the real Photon call.

Keep this signature. Returns True only if Photon accepted the message.
Reminder: on the free shared line you may need to text the Photon line first
before it can message you.
"""
import logging

log = logging.getLogger("photon_send")


def send_imessage(to: str, text: str) -> bool:
    """Send an iMessage to `to` (E.164). STUB: logs and returns False."""
    log.warning("[STUB] send_imessage not implemented. to=%s text=%r", to, text[:80])
    return False
