"""Keep the lifetime of an old projectile separate from new equipment."""
from fixes.bug_descriptions import bug_fix


def emit(c):
    c.label("weapon_owner_pickup")
    c.emit("32 16 C4 F5 E5", "store new equipment / preserve af and hl")
    for base in (0xC450, 0xC460):
        c.emit("3A " + base.to_bytes(2, "little").hex(" "), "ld a,(projectile_phase)")
        c.emit("21 " + (base + 1).to_bytes(2, "little").hex(" ") + " B6", "or projectile_type")
        c.emit("32 " + (base + 15).to_bytes(2, "little").hex(" "), "mark earlier projectile as no longer owning equipment")
    c.emit("E1 F1 C9", "restore hl and af / ret")
    c.label("weapon_owner_lose")
    c.emit("DD 7E 0F B7 C0 AF 32 16 C4", "reject an earlier owner / otherwise clear equipment")
    c.jp(0x8E9A)
    c.label("weapon_owner_wall_clear")
    c.call(0x8E93)
    c.jp(0x74E9)


def apply(edit, hook, c):
    hook(0x4D76, "32 16 C4", "weapon_owner_pickup", "Mark existing projectiles when primary equipment is collected")
    hook(0x4E93, "AF 32 16", "weapon_owner_lose", "Preserve newly collected equipment when an earlier projectile ends", 0xC3)
    edit(0x4E96, "C4", "00", "Pad the replaced four-byte equipment-clear entry")
    hook(0x34B5, "CD E9 74", "weapon_owner_wall_clear", "Read ownership before clearing a wall-hit projectile")
    edit(0x34B8, "C3 93 8E", "C9 00 00", "Return after the ordered equipment check and projectile clear")


FIX = bug_fix("weapon_owner", emit_helpers=emit, apply=apply)
