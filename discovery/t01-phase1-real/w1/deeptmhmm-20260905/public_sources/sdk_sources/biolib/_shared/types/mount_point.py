from .typing import TypedDict


class MountPoint(TypedDict):
    target_path: str
    uri: str
