"""Resolve built frontend files without leaving the dist directory."""

from pathlib import Path


def looks_like_file(full_path: str) -> bool:
    return "." in Path(full_path).name


def resolve_dist_file(dist: Path, full_path: str) -> Path | None:
    """Return a file inside dist, or None when the SPA index should be considered.

    Paths that escape dist also return None. Callers must 404 those rather than
    fall back to index.html.
    """
    if not full_path or full_path.startswith(("/", "\\")) or "\\" in full_path:
        return None
    root = dist.resolve()
    candidate = (root / full_path).resolve()
    if candidate != root and root not in candidate.parents:
        return None
    if candidate.is_file():
        return candidate
    return None


def path_escapes(dist: Path, full_path: str) -> bool:
    if not full_path:
        return False
    if full_path.startswith(("/", "\\")) or "\\" in full_path:
        return True
    root = dist.resolve()
    candidate = (root / full_path).resolve()
    return candidate != root and root not in candidate.parents
