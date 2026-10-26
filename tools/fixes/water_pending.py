"""Protect the pending throw selected by the original attack finisher."""
from fixes.bug_descriptions import bug_fix


def emit(c):
    c.label("water_pending_available")
    c.emit("3A 61 C4 B7 C0", "return occupied holy-water slot type")
    c.emit("3A 22 C4 B7", "no current attack: allow even a stale phase-one record")
    c.jr("water_pending_free", "z")
    c.emit("3A 36 C4 FE 02", "only a projectile attack completes a reserved slot")
    c.jr("water_pending_free", "c")
    c.emit("3A 50 C4 3D", "the finisher chooses slot zero first when its phase is one")
    c.jr("water_pending_free", "z")
    c.emit("3A 60 C4 FE 01", "otherwise protect slot one's pending throw")
    c.jr("water_pending_free", "nz")
    c.emit("3E 01 C9", "nonzero availability result rejects this holy-water claim")
    c.label("water_pending_free")
    if "fall_attack" in c.enabled:
        c.emit("21 60 C4 06 10 AF", "retain fall-attack's accepted holy-water record initialization")
        c.label("water_pending_clear")
        c.emit("77 23", "ld (hl),a / inc hl")
        c.branch(0x10, "water_pending_clear", "djnz", True)
    c.emit("AF C9", "xor a / ret ; available")


def apply(edit, hook, c):
    for offset in (0x3194, 0x31A1):
        hook(offset, "3A 61 C4", "water_pending_available", "Protect the current attack's second-slot reservation before a holy-water claim")


FIX = bug_fix("water_pending", emit_helpers=emit, apply=apply)
