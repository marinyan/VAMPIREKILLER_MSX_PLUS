"""Do not treat a holy-water side exit as loss of primary equipment."""
from fixes.bug_descriptions import bug_fix


def emit(c):
    c.label("water_edge_equipment")
    c.emit("DD 7E 01 FE 05 3A 16 C4 C0 AF C9", "load actual projectile type / preserve primary except for its normal owner / ret")


def apply(edit, hook, c):
    hook(0x34DF, "3A 16 C4", "water_edge_equipment", "Skip primary-equipment loss for a holy-water side exit")


FIX = bug_fix("water_edge", emit_helpers=emit, apply=apply)
