"""A fix owns its helper emitter, ROM edits, and selection metadata."""
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class Explanation:
    symptom_ja: str
    symptom_en: str
    trigger_ja: str
    trigger_en: str
    correction_ja: str
    correction_en: str
    notes_ja: str = ""
    notes_en: str = ""

    def text(self, language, *, behavior_change=False):
        if language == "ja":
            sections = (("挙動の説明（挙動改善）" if behavior_change else "バグ説明", self.symptom_ja),
                        ("発生する場面", self.trigger_ja), ("修正後の動作", self.correction_ja),
                        ("補足", self.notes_ja))
        else:
            sections = (("Behavior description (behavior change)" if behavior_change else "Bug description", self.symptom_en),
                        ("When it happens", self.trigger_en), ("With this fix", self.correction_en),
                        ("Notes", self.notes_en))
        return "\n\n".join(f"{heading}\n{body}" for heading, body in sections if body)


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
    explanation: Explanation | None = None
    behavior_change: bool = False
    extended_helpers: bool = False
    bug_ids: tuple[str, ...] = ()

    def title(self, language):
        return self.title_ja if language == "ja" else self.title_en

    def description(self, language):
        return self.description_ja if language == "ja" else self.description_en

    def explanation_text(self, language):
        if self.explanation is None:
            return self.description(language)
        return self.explanation.text(language, behavior_change=self.behavior_change)
