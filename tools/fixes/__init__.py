"""A fix owns its helper emitter, ROM edits, and selection metadata."""
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class Fix:
    id: str
    title_ja: str
    title_en: str
    description_ja: str
    description_en: str
    emit_helpers: Callable | None = None
    apply: Callable | None = None
    requires: tuple[str, ...] = ()
    conflicts: tuple[str, ...] = ()

    def title(self, language):
        return self.title_ja if language == "ja" else self.title_en

    def description(self, language):
        return self.description_ja if language == "ja" else self.description_en
