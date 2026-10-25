"""Optional progress callbacks, independent of any host application."""

from typing import Protocol


class DownloadObserver(Protocol):
    def progress(self, *, stage: str, message: str, pct: float) -> None: ...
