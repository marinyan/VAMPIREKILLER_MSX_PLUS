"""Route terrain notifications to the projectile returned in IY."""
from fixes.bug_descriptions import bug_fix


def emit(c):
    c.label("axe_wall_notify")
    c.emit("32 33 C4 F5 FD 7E 01 FE 03", "keep shared notification / preserve af / test actual projectile type")
    c.jr("axe_wall_notify_other", "nz")
    c.emit("F1 FD 77 0E C9", "restore af / ld (iy+14),a / ret")
    c.label("axe_wall_notify_other")
    c.emit("F1 C9", "pop af / ret")
    c.label("axe_wall_pointer")
    c.emit("DD E5 E1 7D C6 0E 6F C9", "point hl at the current axe's notification byte / ret")


def apply(edit, hook, c):
    hook(0x40BF, "32 33 C4", "axe_wall_notify", "Notify the actual colliding axe without modifying the terrain record")
    hook(0x348C, "21 33 C4", "axe_wall_pointer", "Read the current axe's own terrain notification")


FIX = bug_fix("axe_wall", emit_helpers=emit, apply=apply)
