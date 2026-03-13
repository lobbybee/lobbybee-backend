"""Helpers for guest name formatting in user-facing messages."""


def get_first_name_from_full_name(full_name, default="Guest"):
    """
    Return the first token from a full name.

    Rules:
    - Trim leading/trailing whitespace.
    - Split at the first space.
    - Fallback to `default` when value is empty.
    """
    normalized_name = (full_name or "").strip()
    if not normalized_name:
        return default
    return normalized_name.split(" ", 1)[0]
