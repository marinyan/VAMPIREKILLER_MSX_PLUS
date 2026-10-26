"""Weapons during falls: resident helpers and original-ROM hooks."""
import struct

from fixes import Explanation, Fix


def emit_helpers(c):
    c.label("special_state")
    c.emit("3A 20 C4 FE 04 C0 3E 01 C9", "ld a,($C420) / cp 4 / ret nz / ld a,1 / ret")
    c.label("fall_pose")
    c.emit("3A 22 C4 B7 C0", "ld a,($C422) / or a / ret nz")
    c.emit("11 00 00 ED 53 2E C4", "ld de,0 / ld ($C42E),de")
    c.jp(0x765F)
    # Both left/right holy-water inputs share this ownership guard.
    c.label("holy_water_slot")
    c.emit("3A 61 C4 B7 C0", "ld a,($C461) / or a / ret nz")
    c.emit("3A 60 C4 3D", "ld a,($C460) / dec a")
    c.jr("holy_free", "nz")
    c.emit("3A 22 C4 B7", "ld a,($C422) / or a")
    c.jr("holy_free", "z")
    c.emit("3A 50 C4 3D", "ld a,($C450) / dec a")
    c.jr("holy_busy", "nz")
    c.emit("3A 51 C4 B7 C0", "ld a,($C451) / or a / ret nz")
    c.label("holy_free")
    c.emit("21 60 C4 06 10 AF", "ld hl,$C460 / ld b,16 / xor a")
    c.label("holy_clear")
    c.emit("77 23", "ld (hl),a / inc hl")
    c.branch(0x10, "holy_clear", "djnz", True)
    c.emit("C9", "ret")
    c.label("holy_busy")
    c.emit("3E 01 C9", "ld a,1 / ret")


def apply(edit, hook, c):
    hook(0x3136, "3A 20 C4", "special_state", "Allow special weapons in natural-fall state")
    edit(0x31E9, "04", "05", "Advance attacks in state 4; keep hurt/death restrictions")
    pose = b"\xcd" + struct.pack("<H", c.labels["fall_pose"]) + b"\x00" * 7
    edit(0x2F48, "11 00 00 ED 53 2E C4 CD 5F 76", pose, "Preserve active attack poses during falling")
    if "water_pending" not in getattr(c, "enabled", ()):
        hook(0x3194, "3A 61 C4", "holy_water_slot", "Guard and clear left holy-water slot")
        hook(0x31A1, "3A 61 C4", "holy_water_slot", "Guard and clear right holy-water slot")


FIX = Fix(
    id='fall_attack',
    title_ja='落下中の武器使用', title_en='Weapons during falls',
    description_ja='足場から落下している間も、鞭と特殊武器を使用できます。',
    description_en='Use the whip and special weapons while falling off a ledge.',
    emit_helpers=emit_helpers, apply=apply,
    bug_ids=("msx.fall_attack",),
    explanation=Explanation(
        symptom_ja=("足場から歩いて落ちると、地上で始めた鞭などの攻撃が着地するまで途中で止まります。"
                    "また、落下中に特殊武器を使おうとしても受け付けられません。ジャンプ中にはできる攻撃が、"
                    "歩いて落ちた場合には続かないという違いがあります。"),
        symptom_en=("When you walk off a ledge, an attack started on the ground stops progressing until you land. "
                    "Special-weapon input is also rejected during that fall. Attacks that work during a jump "
                    "therefore stop or become unavailable when you fall by walking off an edge."),
        trigger_ja="足場の端から歩いて落ちる前後に攻撃する、またはその落下中に特殊武器を使う操作をします。",
        trigger_en="Attack just before walking off a ledge, or try to use a special weapon during the resulting fall.",
        correction_ja=("歩いて落ちている間も攻撃の動きと表示が進み、鞭・剣・斧・十字架・聖水・砂時計を使えます。"
                       "発射待ちの剣があるときに、聖水がその枠を上書きすることも防ぎます。"),
        correction_en=("Attacks continue progressing and displaying during the fall, and the whip, sword, axe, cross, "
                       "holy water, and stopwatch remain usable. Holy water also cannot overwrite a sword slot "
                       "that is still waiting to launch."),
        notes_ja="落下速度、着地の判定と音は変えません。被弾中や死亡中の攻撃制限も維持します。",
        notes_en="Falling speed, landing detection and sound, and the attack restrictions during injury or death are preserved.",
    ),
)
