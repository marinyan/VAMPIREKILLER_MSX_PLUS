"""Initialization of independent projectile metadata in expanded builds."""


def emit_claims(c):
    offsets = ([13] if "screen_edges" in c.enabled else []) + ([14] if "axe_wall" in c.enabled else []) + ([15] if "weapon_owner" in c.enabled else [])
    c.label("projectile_new_claim")
    c.emit("DD 77 00", "ld (ix+0),a ; original pending reservation")
    for offset in offsets:
        c.emit(f"DD 36 {offset:02X} 00", "clear selected projectile metadata")
    c.emit("C9", "ret")
    c.label("projectile_holy_claim")
    c.emit("F5 AF", "push af / xor a")
    for offset in offsets:
        c.emit("32 " + (0xC460 + offset).to_bytes(2, "little").hex(" "), "clear selected holy-water metadata")
    c.emit("F1", "pop af")
    c.jp(0x999F)


def apply_claims(edit, hook):
    hook(0x31D4, "DD 77 00", "projectile_new_claim", "Initialize metadata on a newly accepted projectile reservation")
    hook(0x31AA, "CD 9F 99", "projectile_holy_claim", "Initialize metadata for a new holy-water claim")
