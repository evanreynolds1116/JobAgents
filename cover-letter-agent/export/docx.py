"""Exporter: approved letter -> .docx / .pdf in output/.

Milestone 4 adds the approval gate; Milestone 5 adds the actual export.
"""

EXPORTABLE = ("approved", "submitted")


class NotApproved(Exception):
    """Final export is only for letters you've approved."""


def can_export(app: dict) -> bool:
    return app.get("status") in EXPORTABLE and app.get("sent_version") is not None


def require_approved(app: dict) -> None:
    if not can_export(app):
        raise NotApproved("Approve the letter before exporting it. Drafts can be copied, not exported.")
