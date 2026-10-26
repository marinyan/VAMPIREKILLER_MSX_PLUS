"""Skip only the gate collision query when the room has no gate."""
from fixes.bug_descriptions import bug_fix


def emit(c):
    c.label("gate_if_present")
    c.emit("3A AC C5 B7 C8", "no gate: return with carry clear and leave coordinates intact")
    c.jp(0x8580)


def apply(edit, hook, c):
    hook(0x2C7C, "CD 80 85", "gate_if_present", "Do not collide with a nonexistent gate at the origin")


FIX = bug_fix("phantom_gate", emit_helpers=emit, apply=apply)
