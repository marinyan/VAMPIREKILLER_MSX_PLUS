"""Display each flying primary weapon from its own type and current pose.

The input ROM supplies every image. Four unused hardware pattern slots are
borrowed for one displayed update, then restored before the next game update.
C4F0..C4F4 is outside the eight static records at C470..C4EF. The 128-byte
backup uses otherwise unused upper VRAM at 10000..1007F.
"""
from fixes import Explanation, Fix


def weapon_patterns(source):
    """Reproduce the original three RLE transfers and their horizontal flips."""
    result = bytearray()
    for weapon in (2, 3, 4):
        offset = 0x15D7 + (weapon - 2) * 2
        pointer = int.from_bytes(source[offset:offset + 2], "little")
        decoded = bytearray()
        for _ in range(4096):
            offset = 10 * 8192 + pointer - 0xA000
            control = source[offset]
            pointer += 1
            if control == 0:
                break
            if control == 128:
                pointer = int.from_bytes(source[offset + 1:offset + 3], "little")
            elif control & 128:
                count = control & 127
                decoded += source[offset + 1:offset + 1 + count]
                pointer += count
            else:
                decoded += bytes((source[offset + 1],)) * control
                pointer += 1
        else:
            raise ValueError("Weapon image transfer did not terminate")
        expected = 64 if weapon == 2 else 128
        if len(decoded) != expected:
            raise ValueError("Unexpected weapon image size")
        image = bytearray(256)
        image[:expected] = decoded

        def flip(block):
            reverse = lambda value: int(f"{value:08b}"[::-1], 2)
            return b"".join(bytes(reverse(value) for value in block[start + 16:start + 32]) +
                            bytes(reverse(value) for value in block[start:start + 16])
                            for start in (0, 32))

        if weapon == 2:
            image[64:128] = flip(image[:64])
        else:
            image[128:192] = flip(image[64:128])
            image[192:256] = flip(image[:64])
        result += image
    return bytes(result)


def emit(c):
    c.label("weapon_graphics_frame")
    c.emit("F5 3A 00 C0 FE 0B", "preserve af / a paused frame retains its cached patterns")
    c.jr("weapon_graphics_dispatch", "z")
    c.call("weapon_graphics_restore")
    c.label("weapon_graphics_dispatch")
    c.emit("F1", "restore af before the original game dispatch")
    c.call(0x414D)
    c.emit("F5 C5 D5 E5 DD E5 FD E5 3A 00 C0 FE 05", "preserve the original result / ordinary gameplay")
    c.jr("weapon_graphics_compose", "z")
    c.emit("FE 0B", "paused gameplay")
    c.jr("weapon_graphics_other_mode", "nz")
    c.emit("3A F0 C4 B7", "an unchanged pause keeps its already composed SAT")
    c.jr("weapon_graphics_frame_done", "nz")
    c.label("weapon_graphics_compose")
    c.call("weapon_graphics_restore")
    c.call("weapon_graphics_apply")
    c.jr("weapon_graphics_frame_done")
    c.label("weapon_graphics_other_mode")
    c.call("weapon_graphics_restore")
    c.label("weapon_graphics_frame_done")
    c.emit("FD E1 DD E1 E1 D1 C1 F1 C9", "restore original result / ret")

    c.label("weapon_graphics_restore")
    c.emit("F5 3A F0 C4 B7", "restore borrowed patterns only when a cache exists")
    c.jr("weapon_graphics_restore_empty", "z")
    c.emit("FE 05", "valid cache contains at most four patterns")
    c.jr("weapon_graphics_restore_valid", "c")
    c.emit("AF 32 F0 C4", "discard an invalid cache count")
    c.label("weapon_graphics_restore_empty")
    c.emit("F1 C9", "restore af / ret")
    c.label("weapon_graphics_restore_valid")
    c.emit("C5 D5 E5 DD E5 FD E5 47", "save registers / b = pattern count")
    c.emit("21 E0 FF 39 F9 E5 FD E1 DD 21 F1 C4", "32-byte transfer buffer / ix = borrowed pattern ids")
    c.label("weapon_graphics_restore_one")
    c.emit("C5 DD E5 E1 7D D6 F1 07 07 07 07 07 6F 26 00 FD E5 D1", "backup index times32 / buffer destination")
    c.call("weapon_graphics_read_backup")
    c.emit("DD 6E 00 26 00 29 29 29 7C C6 F8 67 EB FD E5 E1 01 20 00 CD 75 46", "restore the original 32-byte pattern")
    c.emit("DD 23 C1 05", "next cached pattern")
    c.branch(0xC2, "weapon_graphics_restore_one", "jp nz,")
    c.call("display_restore_sat")
    c.emit("21 F0 C4 06 05 AF", "clear the five reserved cache bytes")
    c.label("weapon_graphics_clear_metadata")
    c.emit("77 23", "clear byte / advance")
    c.branch(0x10, "weapon_graphics_clear_metadata", "djnz", True)
    c.emit("21 20 00 39 F9 FD E1 DD E1 E1 D1 C1 F1 C9", "release buffer / restore all registers / ret")

    c.label("weapon_graphics_apply")
    c.emit("3A 51 C4 D6 02 FE 03", "is the first record a primary projectile type2..4?")
    c.jr("weapon_graphics_allocate", "c")
    c.emit("3A 61 C4 D6 02 FE 03 D0", "otherwise return unless the second record is a primary projectile")
    c.label("weapon_graphics_allocate")
    c.emit("21 A0 FF 39 F9 E5 FD E1 54 5D 13 01 3F 00 36 00 ED B0", "96 stack bytes: 64 used-slot flags and a 32-byte transfer buffer")
    c.emit("21 02 D6 06 20", "mark every pattern referenced by the 32 original SAT records")
    c.label("weapon_graphics_mark_used")
    c.emit("E5 7E 0F 0F E6 3F 5F 16 00 FD E5 E1 19 36 01 E1 23 23 23 23", "used[pattern /4] = 1 / next SAT record")
    c.branch(0x10, "weapon_graphics_mark_used", "djnz", True)
    c.emit("AF 32 F0 C4 DD 21 50 C4 06 02", "empty cache / visit the two unchanged projectile records")
    c.label("weapon_graphics_slot")
    c.emit("C5 DD 7E 00 FE 02", "save slot loop / pending or free records have no visible primary image")
    c.branch(0xDA, "weapon_graphics_slot_done", "jp c,")
    c.emit("DD 7E 01 D6 02 FE 03", "only primary types2..4")
    c.branch(0xD2, "weapon_graphics_slot_done", "jp nc,")
    c.emit("DD 7E 06 D6 18 FE 20", "only original pose starts24,32,40,48")
    c.branch(0xD2, "weapon_graphics_slot_done", "jp nc,")
    c.emit("E6 07", "pose is aligned to its two-layer pair")
    c.branch(0xC2, "weapon_graphics_slot_done", "jp nz,")
    c.emit("0E 00", "first color layer")
    c.label("weapon_graphics_layer")
    c.emit("C5 FD E5 E1 1E 00", "save layer / find an unused one of the64 hardware pattern slots")
    c.label("weapon_graphics_find_free")
    c.emit("7E B7", "is this pattern slot unused?")
    c.jr("weapon_graphics_found_free", "z")
    c.emit("23 1C", "advance slot and index")
    c.jr("weapon_graphics_find_free")
    c.label("weapon_graphics_found_free")
    c.emit("36 01 7B 07 07 4F 3A F0 C4 C6 F1 6F 26 C4 71", "claim slot and remember its aligned pattern number")
    c.emit("69 26 00 29 29 29 7C C6 F8 67 E5 FD E5 E1 11 40 00 19 EB E1 01 20 00 CD 5A 46", "read the unused pattern into the transfer buffer")
    c.emit("FD E5 E1 11 40 00 19 3A F0 C4 07 07 07 07 07 5F 16 00", "source buffer / upper-VRAM backup index times32")
    c.call("weapon_graphics_write_backup")
    c.emit("C1 C5 DD 7E 01 D6 02 67 DD 7E 06 D6 18 07 07 07 6F 79 B7", "type and pose select the input-ROM image; c selects its color layer")
    c.jr("weapon_graphics_asset_start", "z")
    c.emit("11 20 00 19", "second color layer offset")
    c.label("weapon_graphics_asset_start")
    c.branch(0x11, "weapon_graphics_images", "ld de,")
    c.emit("19 E5 3A F0 C4 C6 F1 6F 26 C4 6E 26 00 29 29 29 7C C6 F8 67 EB E1 01 20 00 CD 75 46", "copy the correct 32-byte image to the borrowed slot without changing the shared image bank")
    c.emit("DD E5 E1 7D FE 50 3E 03", "logical SAT pair3 belongs to projectile0")
    c.jr("weapon_graphics_sat_pair", "z")
    c.emit("3E 04", "logical SAT pair4 belongs to projectile1")
    c.label("weapon_graphics_sat_pair")
    c.call("display_sat_pair")
    c.emit("5F 16 F6", "displayed SAT pair address, honoring linear boss priority")
    c.emit("C1 C5 79 07 07 C6 02 83 5F 3A F0 C4 C6 F1 6F 26 C4 7E EB CD A1 46", "write only the displayed SAT pattern byte; leave coordinates, colors and RAM records intact")
    c.emit("21 F0 C4 34 C1 0C 79 FE 02", "commit this cached pattern / next color layer")
    c.branch(0xDA, "weapon_graphics_layer", "jp c,")
    c.label("weapon_graphics_slot_done")
    c.emit("C1 11 10 00 DD 19 05", "next original projectile slot")
    c.branch(0xC2, "weapon_graphics_slot", "jp nz,")
    c.emit("21 60 00 39 F9 C9", "release temporary buffers / ret")

    c.label("weapon_graphics_read_backup")
    c.emit("3A 07 00 3C 4F F3 3E 04 ED 79 3E 8E ED 79 7D ED 79 AF ED 79", "select upper VRAM and the backup read address")
    c.emit("3A 06 00 4F EB 06 20 ED B2 FB C9", "read32 bytes to the RAM transfer buffer / ei / ret")
    c.label("weapon_graphics_write_backup")
    c.emit("3A 07 00 3C 4F F3 3E 04 ED 79 3E 8E ED 79 7B ED 79 3E 40 ED 79", "select upper VRAM and the backup write address")
    c.emit("3A 07 00 4F 06 20 ED B3 FB C9", "save32 original pattern bytes / ei / ret")
    c.label("weapon_graphics_images")
    c.emit(weapon_patterns(c.source).hex(" "), "weapon images derived from the supplied original ROM")


def apply(edit, hook, c):
    hook(0x0058, "CD 4D 41", "weapon_graphics_frame", "Preserve flying weapons' own images across equipment and pose transfers")


FIX = Fix(
    "weapon_graphics", "飛行中の武器の画像を保つ", "Flying weapon image ownership",
    "装備を持ち替えても、飛行中の武器が別の武器の画像へ変わらないようにします。",
    "Keep a flying weapon's image when another primary weapon is equipped.",
    emit_helpers=emit, apply=apply, extended_helpers=True, behavior_change=True,
    explanation=Explanation(
        symptom_ja="投げた剣などが画面に残っている間に別の武器へ持ち替えると、共有している画像が上書きされ、以前の武器の軌道のまま新しい武器の絵で飛ぶことがあります。",
        symptom_en="Changing equipment while a thrown weapon remains can overwrite its shared image, making the old projectile fly along its original trajectory with the new weapon's appearance.",
        trigger_ja="飛行中の主武器が残る状態で、別種類の主武器を取得したり、共有画像を更新する攻撃へ移ったときです。",
        trigger_en="Collect a different primary weapon, or perform an attack that refreshes the shared patterns, while an earlier primary projectile is still flying.",
        correction_ja="各投射枠の武器種と現在の絵に応じて画像を表示します。使用中のスプライト画像枠は避け、借りた画像領域は次のゲーム更新より前に元へ戻します。飛行・反転・当たり判定・装備の取得や喪失、聖水と敵の画像は変えません。",
        correction_en="Display each projectile from its own type and pose. Borrow only unreferenced sprite-pattern slots and restore them before the next game update. Preserve trajectories, reversals, collisions, equipment ownership, holy water, and enemy images.",
        notes_ja="表示の改善項目です。画像は入力された原版ROMから生成し、配布ツールには画像データを収録しません。",
        notes_en="This is a display improvement. Images are generated from the supplied original ROM; the distributed tool contains no image data."))
