"""Shared-password check. The secret is never logged."""

import hashlib
import hmac


def secret_matches(provided: str, expected: str) -> bool:
    # Hash both sides so the compare is fixed-length.
    return hmac.compare_digest(
        hashlib.sha256(provided.encode("utf-8")).digest(),
        hashlib.sha256(expected.encode("utf-8")).digest(),
    )
