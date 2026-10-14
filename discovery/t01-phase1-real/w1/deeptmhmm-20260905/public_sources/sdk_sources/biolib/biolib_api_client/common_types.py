from biolib._shared.types.typing import TypedDict


class SemanticVersion(TypedDict):
    major: int
    minor: int
    patch: int
