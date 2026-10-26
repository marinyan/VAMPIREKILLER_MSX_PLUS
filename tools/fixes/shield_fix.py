"""Shield durability: resident helpers and original-ROM hooks."""
from fixes import Explanation, Fix


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
    bug_ids=("msx.shield_area", "msx.shield_break"),
    explanation=Explanation(
        symptom_ja=("この項目は盾に関する2つの不具合をまとめて直します。\n"
                    "① 盾を持ったまま通常のステージを移動すると、装備は残るのに残り耐久だけが0になります。"
                    "そのまま防御すると0から255へ戻り、本来より長く使えてしまいます。\n"
                    "② 弾を防ぐ盾が最後の耐久を使い切っても、同じ処理で重なった残りの弾まで防ごうとし、"
                    "耐久が再び0から255へ戻ることがあります。"),
        symptom_en=("This item fixes two shield bugs.\n"
                    "1. An ordinary area transition leaves the shield equipped but resets its remaining durability to zero. "
                    "The next block wraps zero to 255, allowing far more uses than intended.\n"
                    "2. When a projectile-blocking shield uses its last charge, it can continue blocking other projectiles "
                    "in the same update and wrap durability from zero to 255 again."),
        trigger_ja=("盾を装備して白い鍵で通常のステージを移動し、その後に防御します。"
                    "もう一方は、弾を防ぐ盾の残り耐久が1のときに複数の弾が同時に重なると発生します。"),
        trigger_en=("Carry a shield through a white-key area transition and then block an attack. "
                    "The second bug occurs when multiple projectiles overlap a projectile shield with one charge left."),
        correction_ja=("通常のステージ移動では残り耐久をそのまま持ち越します。最後の1回を使った盾は解除し、"
                       "その盾で同時に重なった残りの弾まで防ぎません。耐久0の盾による0→255の巻き戻りも防ぎます。"),
        correction_en=("Ordinary area changes retain the remaining charges. A shield is removed after its final use, "
                       "and it does not block the remaining projectiles in that update. An exhausted shield cannot "
                       "wrap zero durability to 255."),
        notes_ja=("接触ダメージを減らす盾と、弾を防ぐ盾の両方が対象です。取得時は16回分です。"
                  "ボス撃破後やミス後には、通常どおり盾を外し、耐久も0にします。"),
        notes_en=("Both the contact-damage reduction shield and projectile-blocking shield are covered. "
                  "A new shield has 16 charges. Boss clears and lost lives still remove the equipment and clear durability."),
    ),
)
