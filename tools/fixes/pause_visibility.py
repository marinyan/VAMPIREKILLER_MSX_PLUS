"""Temporarily mask sprites intersecting the pause message in the VDP SAT."""
from fixes import Explanation, Fix


def emit(c):
    c.label("pause_visible_enter")
    c.call(0x4495)
    c.emit("F5 C5 D5 E5 DD E5 FD E5", "preserve the original pause-draw result")
    c.emit("21 70 FF 39 F9 E5 FD E1", "reserve 144 stack bytes / iy = SAT buffer")
    c.emit("11 80 00 19 E5 DD E1", "ix = 16-byte color buffer")
    c.emit("FD E5 D1 21 00 F6 01 80 00 CD 5A 46", "read the displayed 128-byte SAT")
    c.emit("21 00 F4 0E 20", "hl = displayed color table / 32 sprite records")
    c.label("pause_sprite_next")
    c.emit("C5 E5 FD 7E 00 FE D8", "save loop / read SAT y / stop marker")
    c.branch(0xCA, "pause_sprite_stop", "jp z,")
    c.emit("FE 44", "cp 68 ; 16-pixel sprite intersects y84..99")
    c.branch(0xDA, "pause_sprite_skip", "jp c,")
    c.emit("FE 63", "cp 99")
    c.branch(0xD2, "pause_sprite_skip", "jp nc,")
    c.emit("FD 7E 01 FE 59", "SAT x must intersect normally or with early clock")
    c.branch(0xDA, "pause_sprite_skip", "jp c,")
    c.emit("FE B8", "cp 184")
    c.branch(0xD2, "pause_sprite_skip", "jp nc,")
    c.emit("3E 53 FD 96 00", "first overlapping color row = max(0,83-SAT_y)")
    c.jr("pause_row_start", "nc")
    c.emit("AF", "xor a")
    c.label("pause_row_start")
    c.emit("4F 3E 63 FD 96 00 FE 10", "last row exclusive = min(16,99-SAT_y)")
    c.jr("pause_row_end", "c")
    c.emit("3E 10", "ld a,16")
    c.label("pause_row_end")
    c.emit("91 47 C5 DD E5 D1 01 10 00 CD 5A 46 C1", "save row span / read color rows / restore span")
    c.emit("DD E5 E1 59 16 00 19", "hl = color buffer + first overlapping row")
    c.label("pause_color_row")
    c.emit("CB 7E FD 7E 01", "test this scanline's early-clock bit / load SAT x")
    c.jr("pause_early_clock", "nz")
    c.emit("FE 98", "normal x <152 intersects the message")
    c.jr("pause_hide_sprite", "c")
    c.jr("pause_color_continue")
    c.label("pause_early_clock")
    c.emit("FE 79", "early-clock x >=121 intersects after subtracting32")
    c.jr("pause_hide_sprite", "nc")
    c.label("pause_color_continue")
    c.emit("23", "inc hl")
    c.branch(0x10, "pause_color_row", "djnz", True)
    c.jr("pause_sprite_skip")
    c.label("pause_hide_sprite")
    c.emit("FD 36 00 E0", "hide only this hardware sprite while paused")
    c.label("pause_sprite_skip")
    c.emit("E1 11 10 00 19 C1 11 04 00 FD 19 0D", "advance color/SAT pointers / dec sprite count")
    c.branch(0xC2, "pause_sprite_next", "jp nz,")
    c.jr("pause_sat_write")
    c.label("pause_sprite_stop")
    c.emit("E1 C1", "discard the saved loop at the SAT terminator")
    c.label("pause_sat_write")
    c.emit("21 00 00 39 11 00 F6 01 80 00 CD 75 46", "upload masked SAT; leave the game RAM mirror intact")
    c.emit("21 90 00 39 F9 FD E1 DD E1 E1 D1 C1 F1 C9", "release buffer / restore original result / ret")

    c.label("pause_visible_leave")
    c.call(0x44B8)
    c.emit("F5 C5 D5 E5 DD E5 FD E5", "preserve the original background-restore result")
    c.call("display_restore_sat")
    c.emit("FD E1 DD E1 E1 D1 C1 F1 C9", "preserve the background-restore result / ret")


def apply(edit, hook, c):
    hook(0x028C, "CD 95 44", "pause_visible_enter", "Keep overlapping sprites behind the pause message")
    hook(0x03E3, "CD B8 44", "pause_visible_leave", "Restore the paused sprites before gameplay resumes")


FIX = Fix(
    "pause_visibility", "PAUSE文字を見やすくする", "Readable pause message",
    "PAUSE文字の範囲に重なるスプライトを、ポーズ中だけ隠します。",
    "Hide sprites intersecting the pause message until play resumes.",
    emit_helpers=emit, apply=apply, extended_helpers=True, behavior_change=True,
    explanation=Explanation(
        symptom_ja="PAUSE文字は背景へ描かれるため、停止した主人公・敵・武器のスプライトが重なると文字を隠すことがあります。",
        symptom_en="The pause message is drawn into the background, so a stopped player, enemy, or weapon sprite can cover it.",
        trigger_ja="画面中央付近で、スプライトがPAUSE文字の48×16ドットの領域へ重なった状態でポーズします。",
        trigger_en="Pause while a sprite intersects the message's 48 by 16 pixel rectangle near the center of the screen.",
        correction_ja="文字と重なるハードウェアスプライトだけを一時的に非表示にします。横位置を32ドットずらす表示属性も行ごとに確認し、解除時に元の表示順と座標を復元します。ゲーム中の座標・攻撃状態・音源へのポーズ要求は変えません。",
        correction_en="Temporarily hide only intersecting hardware sprites, checking each overlapping scanline's 32-pixel early-clock shift. Restore the original order and coordinates on resume without changing gameplay state or sound pause requests.",
        notes_ja="表示の改善項目です。スプライト枠を追加せず、文字領域外のスプライトと、文字の背景保存・復元を維持します。",
        notes_en="This is a display improvement. It adds no sprite slots and preserves sprites outside the message and the original background save/restore."))
