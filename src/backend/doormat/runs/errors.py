"""Domain errors for cooperative run cancellation."""


class CooperativeCancel(Exception):
    """Raised when the user requests stop and the current work unit has completed."""
