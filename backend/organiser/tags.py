"""Tag text stored as a comma-separated list of normalised tokens."""

MAX_TAGS = 20
MAX_TAG_LENGTH = 40


def clean_tags(tags: list[str]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in tags:
        tag = " ".join(raw.strip().lower().split())
        if not tag:
            continue
        if len(tag) > MAX_TAG_LENGTH:
            raise ValueError(f"Tags must be {MAX_TAG_LENGTH} characters or fewer")
        if any(char in tag for char in ",\n\r\t"):
            raise ValueError("Tags cannot contain commas or line breaks")
        if tag in seen:
            continue
        seen.add(tag)
        cleaned.append(tag)
    if len(cleaned) > MAX_TAGS:
        raise ValueError(f"A note can have at most {MAX_TAGS} tags")
    return cleaned


def clean_one_tag(tag: str) -> str:
    cleaned = clean_tags([tag])
    if len(cleaned) != 1:
        raise ValueError("Provide one tag")
    return cleaned[0]


def join_tags(tags: list[str]) -> str:
    return ",".join(tags)


def split_tags(stored: str | None) -> list[str]:
    if not stored:
        return []
    return [part for part in stored.split(",") if part]
