"""Shield durability: resident helpers and original-ROM hooks."""
from fixes import Fix


def emit_helpers(c):
    c.label("shield_stage_clear")
    c.emit("F5 3A 41 C4 F5", "push af / ld a,($C441) / push af")
    c.call(0x63B7)
    c.emit("F1 32 41 C4", "pop af / ld ($C441),a ; carry remaining durability across area entry")
    c.call("shield_inventory")
    c.emit("F1 C9", "pop af / ret")
    c.label("shield_inventory")
    c.emit("3A 41 C4 B7 3A 01 C7 C0", "ld a,($C441) / or a / ld a,($C701) / ret nz")
    c.emit("E6 CF 32 01 C7 C9", "and $CF / ld ($C701),a / ret ; exhausted shields cannot wrap to255")
    c.label("shield_projectiles_done")
    c.call(0x8EE6)
    c.emit("C1 C9", "pop bc / ret ; stop the collision pass when the shield breaks")


def apply(edit, hook, c):
    hook(0x22EC, "CD B7 63", "shield_stage_clear", "Preserve shield durability during area entry")
    hook(0x4179, "3A 01 C7", "shield_inventory", "Reject an exhausted contact shield before reducing damage")
    hook(0x4610, "3A 01 C7", "shield_inventory", "Reject an exhausted projectile shield before collision checks")
    hook(0x463F, "CD E6 8E", "shield_projectiles_done", "Stop blocking further projectiles after the final shield use", 0xC3)


FIX = Fix(
    id='shield_fix',
    title_ja='盾の耐久修正', title_en='Shield durability',
    description_ja='通常のステージ移動で耐久を持ち越し、ボス後の解除と耐久切れを正常に処理します。',
    description_en='Keep durability across ordinary area changes; correct exhaustion and preserve equipment removal after bosses.',
    emit_helpers=emit_helpers, apply=apply,
)
