"""Z80 hooks for the supported 128 KiB Vampire Killer cartridge dump.

Only the exact input revision is accepted. Helpers live in E618..E7FF and
F100..F1C8, outside the game stack, image buffer and BIOS work areas.
The startup loader runs after RAM clearing and mapper initialization.
"""
from __future__ import annotations

import hashlib
import struct
from compact_assets import ATLAS_END, POSE_START, POSE_TABLE, physical, repack

SOURCE_SHA256 = "99eabaaeb2b6c02220e131043d5a6401d0d8c5f413d89204547adcc04d65e7e2"
RAM_BASE = 0xE618
RAM_END = 0xE800
SIDE_BASE = 0xF100
SIDE_END = 0xF1C9
LOADER_OFFSET = 0x7FC0
LOADER_ADDRESS = 0xBFC0
OUTPUT_SIZE = 0x20000
VARIANTS = {"fall_attack": (True, False), "screen_edges": (False, True), "combined": (True, True)}


class Code:
    """Small label/fixup writer; every opcode is accompanied by its mnemonic."""

    def __init__(self, base):
        self.base, self.data, self.labels, self.fixups, self.lines = base, bytearray(), {}, [], []
        self.segments, self.records = [(0, base)], []

    def address(self, offset):
        start, base = next((start, base) for start, base in reversed(self.segments) if start <= offset)
        return base + offset - start

    def org(self, address):
        self.segments.append((len(self.data), address))
        self.lines.append(f"; org ${address:04X}")

    def label(self, name):
        if name in self.labels:
            raise ValueError(f"Duplicate label: {name}")
        self.labels[name] = self.address(len(self.data))
        self.lines.append(f"{name}:")

    def emit(self, hex_bytes, mnemonic):
        raw = bytes.fromhex(hex_bytes)
        self.records.append((len(self.lines), len(self.data), len(raw)))
        self.lines.append(f"    ; ${self.address(len(self.data)):04X}  {raw.hex(' ').upper()}\n    {mnemonic}")
        self.data.extend(raw)

    def branch(self, opcode, target, mnemonic, relative=False):
        self.emit(f"{opcode:02x} " + ("00" if relative else "00 00"), f"{mnemonic} {target}")
        self.fixups.append((len(self.data) - (1 if relative else 2), target, relative))

    def jp(self, target):
        self.branch(0xC3, target, "jp")

    def call(self, target):
        self.branch(0xCD, target, "call")

    def jr(self, target, condition=None):
        self.branch({None: 0x18, "z": 0x28, "nz": 0x20, "c": 0x38, "nc": 0x30}[condition],
                    target, "jr" + (f" {condition}," if condition else ""), True)

    def finish(self):
        for offset, target, relative in self.fixups:
            address = self.labels[target] if isinstance(target, str) else target
            if relative:
                delta = address - (self.address(offset) + 1)
                if not -128 <= delta <= 127:
                    raise ValueError(f"JR out of range: {target}")
                self.data[offset] = delta & 255
            else:
                self.data[offset:offset + 2] = struct.pack("<H", address)
        for index, start, size in self.records:
            mnemonic = self.lines[index].split("\n", 1)[1]
            raw = self.data[start:start + size]
            self.lines[index] = f"    ; ${self.address(start):04X}  {raw.hex(' ').upper()}\n{mnemonic}"
        return bytes(self.data)


def helpers(fall, edges):
    c = Code(RAM_BASE)
    if fall:
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
    if edges:
        c.label("main_actor")
        c.emit("E5 DD E5 E1 7C E1 FE D7 C9", "compare IX record page with $D7, preserving HL")
        c.label("linear_bullet")
        c.emit("E5 DD E5 E1 7C E1 FE D7", "push hl / push ix / pop hl / ld a,h / pop hl / cp $D7")
        c.jr("not_linear", "c")
        c.emit("DD 7E 00 3D FE 03", "ld a,(ix+0) / dec a / cp 3")
        c.jr("is_linear", "c")
        c.emit("FE 04", "cp 4 ; type 5")
        c.jr("is_linear", "z")
        c.emit("D6 09 FE 02", "sub 9 / cp 2 ; types 10,11")
        c.jr("is_linear", "c")
        c.label("not_linear")
        c.emit("3E 01 B7 C9", "ld a,1 / or a / ret")
        c.label("is_linear")
        c.emit("AF C9", "xor a / ret")
        c.label("projectile_init")
        c.emit("DD 36 7D 00 DD 36 7F 01 C9", "ld (ix+$7D),0 / ld (ix+$7F),1 / ret")
        c.label("spawn_ground")
        c.emit("D5 C5", "push de / push bc")
        c.call("edge_coordinate")
        c.emit("D5", "push de")
        c.call(0x7D2F)
        c.call(0x7C5E)
        c.emit("D1 C1", "pop de / pop bc")
        c.jr("ground_supported", "c")
        c.emit("D1", "pop de ; retain original position when edge has no floor")
        c.jp("spawn_original")
        c.label("ground_supported")
        c.emit("E1", "pop hl ; discard saved original DE")
        c.jp("spawn_original")
        c.label("spawn_flying")
        c.call("edge_coordinate")
        c.jp("spawn_original")
        c.label("edge_coordinate")
        c.emit("7A FE 80 16 00", "ld a,d / cp $80 / ld d,0")
        c.emit("D8 15 C9", "ret c / dec d / ret ; right edge = 255")

        c.label("cull_x")
        c.call("linear_bullet")
        c.jr("bullet_cull", "z")
        c.call("main_actor")
        c.jr("original_cull", "nc")
        c.emit("DD 7E 00 FE 24 C8", "ld a,(ix+0) / cp $24 / ret z ; keep small hearts")
        for kind in (1, 4, 7, 8):
            c.emit(f"FE {kind:02X}", f"cp ${kind:02X}")
            c.jr("enemy_cull", "z")
        c.label("original_cull")
        c.emit("DD 7E 05", "ld a,(ix+5)")
        c.jp(0x99EF)
        c.label("enemy_cull")
        c.emit("DD 7E 05 FE 07", "ld a,(ix+5) / cp 7")
        c.jr("enemy_right", "nc")
        c.emit("DD CB 0A 7E C8", "bit 7,(ix+10) / ret z ; entering from left")
        c.jp(0x99F6)

        c.label("bullet_cull")
        c.emit("DD 7E 7D B7 C8 DD 7E 05", "ld a,(ix+$7D) / or a / ret z / ld a,(ix+5)")
        c.emit("DD CB 0A 7E", "bit 7,(ix+10)")
        c.jr("bullet_left", "nz")
        c.emit("FE 08 D8", "cp 8 / ret c")
        c.jp(0x99F6)
        c.label("bullet_left")
        c.emit("FE F9 D0", "cp $F9 / ret nc")
        c.jp(0x99F6)
        c.label("enemy_right")
        c.emit("FE F1 D8 DD CB 0A 7E C0", "cp $F1 / ret c / bit 7,(ix+10) / ret nz")
        c.jp(0x99F6)

        # Both normal and shared pose tables call this with A = part X offset.
        # Signed offsets vary by pose; preserve each part's actual coordinates.
        c.label("sprite_x")
        c.emit("C5 4F DD 7E 00", "push bc / ld c,a / ld a,(ix+0)")
        c.call("linear_bullet")
        c.jr("sprite_selected", "z")
        c.call("main_actor")
        c.jr("sprite_original", "nc")
        c.emit("DD 7E 00", "ld a,(ix+0)")
        for kind in (1, 4, 7, 8, 0x24):
            c.emit(f"FE {kind:02X}", f"cp ${kind:02X}")
            c.jr("sprite_selected", "z")
        c.label("sprite_original")
        c.emit("79 C1 DD 86 05 C9", "ld a,c / pop bc / add a,(ix+5) / ret")
        c.label("sprite_selected")
        c.emit("E5 2C 2C CB BE", "push hl / inc l / inc l / res 7,(hl)")
        c.call("linear_bullet")
        c.jr("sprite_screen", "nz")
        c.emit("DD 7E 7D B7", "ld a,(ix+$7D) / or a")
        c.jr("sprite_screen", "z")
        c.emit("79 DD 86 05 DD CB 0A 7E", "ld a,c / add a,(ix+5) / bit 7,(ix+10)")
        c.jr("sprite_wrapped_left", "nz")
        c.emit("CB 79", "bit 7,c")
        c.jr("sprite_hide", "z")
        c.jr("sprite_hide", "c")
        c.jr("sprite_done")
        c.label("sprite_wrapped_left")
        c.emit("CB 79", "bit 7,c")
        c.jr("sprite_early", "nz")
        c.jr("sprite_done", "c")
        c.jr("sprite_early")
        c.label("sprite_screen")
        c.emit("CB 79", "bit 7,c ; signed part offset")
        c.jr("sprite_positive", "z")
        c.emit("79 DD 86 05", "ld a,c / add a,(ix+5)")
        c.jr("sprite_done", "c")
        c.jr("sprite_early")
        c.label("sprite_positive")
        c.emit("79 DD 86 05", "ld a,c / add a,(ix+5)")
        c.jr("sprite_done", "nc")
        c.label("sprite_hide")
        c.emit("2D 2D 2D 36 E0 2C 2C 2C", "hide the part Y when its left edge is beyond 255")
        c.jr("sprite_done")
        c.label("sprite_early")
        c.emit("C6 20 CB FE", "add a,32 / set 7,(hl) ; VDP early clock")
        c.label("sprite_done")
        c.emit("E1 C1 C9", "pop hl / pop bc / ret")
        c.label("sprite_shared")
        c.emit("D9", "exx ; access the part record, not the shared ROM coordinates")
        c.call("sprite_x")
        c.emit("D9 C9", "exx / ret")

        c.label("integrate_x")
        c.call("linear_bullet")
        c.jr("bullet_integrate", "z")
        c.emit("DD 7E 00 FE 24", "ld a,(ix+0) / cp $24")
        c.jr("integrate_original", "nz")
        c.emit("CB 7A", "bit 7,d ; signed X velocity")
        c.jr("heart_left", "nz")
        c.emit("19", "add hl,de")
        c.jr("heart_right_limit", "c")
        c.label("heart_bounds")
        c.emit("7C FE F8", "ld a,h / cp $F8")
        c.jr("heart_store", "c")
        c.label("heart_right_limit")
        c.emit("21 00 F8", "ld hl,$F800")
        c.jr("heart_store")
        c.label("heart_left")
        c.emit("19", "add hl,de")
        c.jr("heart_bounds", "c")
        c.emit("21 00 00", "ld hl,0")
        c.jr("heart_store")
        c.label("integrate_original")
        c.emit("19", "add hl,de")
        c.label("heart_store")
        c.emit("DD 75 04 DD 74 05 C9", "ld (ix+4),l / ld (ix+5),h / ret")
        c.label("bullet_integrate")
        c.emit("CB 7A", "bit 7,d")
        c.jr("bullet_integrate_left", "nz")
        c.emit("19", "add hl,de")
        c.jr("heart_store", "nc")
        c.jr("bullet_wrapped")
        c.label("bullet_integrate_left")
        c.emit("19", "add hl,de")
        c.jr("heart_store", "c")
        c.label("bullet_wrapped")
        c.emit("DD 36 7D 01 DD 36 0E 00", "ld (ix+$7D),1 / ld (ix+14),0 ; suppress wrapped collisions")
        c.jr("heart_store")

        c.label("heart_landing_x")
        c.emit("7C FE 04 DD 7E 05 C0 FE F0 D8 3E F0 C9",
               "ld a,h / cp 4 / ld a,(ix+5) / ret nz / cp $F0 / ret c / ld a,$F0 / ret")
        c.label("drop_floor")
        c.emit("DD 7E 00 FE 24", "ld a,(ix+0) / cp $24")
        c.branch(0xC2, 0x7B98, "jp nz,")
        c.call(0x7D2F)
        c.call(0x7C5E)
        c.emit("D8 7A D6 0A", "ret c / ld a,d / sub 10")
        c.jr("drop_second_probe", "nc")
        c.emit("B7 C9", "or a / ret ; no wrapped floor probe")
        c.label("drop_second_probe")
        c.emit("57", "ld d,a")
        c.call(0x7D2F)
        c.jp(0x7C5E)

        c.org(SIDE_BASE)
        c.label("weapon_x")
        c.emit("DD 7E 01 FE 02", "ld a,(ix+1) / cp 2")
        c.jr("weapon_move_original", "nz")
        c.emit("DD CB 03 7E DD 7E 05", "bit 7,(ix+3) / ld a,(ix+5)")
        c.jr("weapon_move_left", "nz")
        c.emit("DD 86 03 D0", "add a,(ix+3) / ret nc")
        c.jr("weapon_wrapped")
        c.label("weapon_move_left")
        c.emit("DD 86 03 D8", "add a,(ix+3) / ret c")
        c.label("weapon_wrapped")
        c.emit("DD 36 0F 01 C9", "ld (ix+15),1 / ret")
        c.label("weapon_move_original")
        c.emit("DD 7E 05 DD 86 03 C9", "ld a,(ix+5) / add a,(ix+3) / ret")
        c.label("weapon_cull")
        c.emit("DD 7E 01 FE 02", "ld a,(ix+1) / cp 2")
        c.jr("weapon_cull_original", "nz")
        c.emit("DD 7E 0F B7 C8 DD 7E 05 DD CB 03 7E", "ld a,(ix+15) / or a / ret z / ld a,(ix+5) / bit 7,(ix+3)")
        c.jr("weapon_cull_left", "nz")
        c.emit("FE 08 D8", "cp 8 / ret c")
        c.jp(0x74E9)
        c.label("weapon_cull_left")
        c.emit("FE F9 D0", "cp $F9 / ret nc")
        c.jp(0x74E9)
        c.label("weapon_cull_original")
        c.emit("DD 7E 05", "ld a,(ix+5)")
        c.jp(0x74DA)
        c.label("weapon_draw")
        c.call(0x7535)
        c.emit("DD 7E 01 FE 02 C0 DD 7E 0F B7", "ld a,(ix+1) / cp 2 / ret nz / ld a,(ix+15) / or a")
        c.jr("weapon_draw_screen", "z")
        c.emit("DD CB 03 7E C8", "bit 7,(ix+3) / ret z")
        c.jr("weapon_early")
        c.label("weapon_draw_screen")
        c.emit("DD 7E 05 FE 08 D0", "ld a,(ix+5) / cp 8 / ret nc")
        c.label("weapon_early")
        c.emit("DD E5 E1 7D FE 50 21 19 D6 11 60 D4", "push ix / pop hl / ld a,l / cp $50 / ld hl,$D619 / ld de,$D460")
        c.jr("weapon_early_slots", "z")
        c.emit("21 21 D6 11 80 D4", "ld hl,$D621 / ld de,$D480")
        c.label("weapon_early_slots")
        c.emit("7E C6 20 77 2C 2C 2C 2C 7E C6 20 77 EB 06 20", "add 32 to both SAT X values / ex de,hl / ld b,32")
        c.label("weapon_color")
        c.emit("CB FE 23", "set 7,(hl) / inc hl")
        c.branch(0x10, "weapon_color", "djnz", True)
        c.emit("C9", "ret")
        # The rectangle dispatcher reads IY+15 before using a sword position.
        c.label("weapon_collision")
        c.emit("3E 06 85 6F", "ld a,6 / add a,l / ld l,a")
        c.emit("FD 7E 01 FE 02", "ld a,(iy+1) / cp 2")
        c.jr("weapon_collision_original", "nz")
        c.emit("FD 7E 0F B7 C0", "ld a,(iy+15) / or a / ret nz ; carry clear")
        c.label("weapon_collision_original")
        c.jp(0x8504)
    return c, bytes(c.data)


def image_loader(address, packed_atlas):
    c = Code(address)
    c.label("image_upload")
    c.emit("C5", "push bc")
    c.emit("11 " + struct.pack("<H", packed_atlas).hex(" "), "ld de,compressed_atlas")
    c.emit("21 00 E8", "ld hl,$E800")
    c.call("unpack")
    c.emit("C1 21 00 E8 C9", "pop bc / ld hl,$E800 / ret")
    c.label("candle_upload")
    c.call(0x4A90)
    c.emit("21 C8 BF 06 01", "ld hl,$BFC8 / ld b,1 ; preserve original fifth-image source")
    c.jp(0x4A90)
    c.label("unpack")
    c.emit("1A 13 B7 C8 CB 7F", "ld a,(de) / inc de / or a / ret z / bit 7,a")
    c.jr("match", "nz")
    c.emit("47", "ld b,a")
    c.label("literals")
    c.emit("1A 13 77 23", "ld a,(de) / inc de / ld (hl),a / inc hl")
    c.branch(0x10, "literals", "djnz", True)
    c.jr("unpack")
    c.label("match")
    c.emit("E6 7F C6 03 47 1A 13 D5 E5 5F 16 00 13 B7 ED 52 EB E1",
           "decode length and distance / save packed cursor / get backward-copy source")
    c.label("copy_match")
    c.emit("1A 13 77 23", "ld a,(de) / inc de / ld (hl),a / inc hl")
    c.branch(0x10, "copy_match", "djnz", True)
    c.emit("D1", "pop de")
    c.jr("unpack")
    return c


def make_rom(source, *, fall, edges):
    if len(source) != 0x20000 or hashlib.sha256(source).hexdigest() != SOURCE_SHA256:
        raise ValueError("Unsupported input ROM. Expected 128 KiB SHA-256 " + SOURCE_SHA256)
    if not (fall or edges):
        raise ValueError("Select at least one improvement")
    c, _ = helpers(fall, edges)
    if edges:
        c.labels["spawn_original"] = 0x5F1D
    payload = c.finish()
    table, poses, atlas, asset_info = repack(source)
    atlas_address = POSE_START + len(poses)
    payload_address = atlas_address + len(atlas)
    codec = image_loader(payload_address + len(payload), atlas_address)
    codec_bytes = codec.finish()
    used_end = codec.base + len(codec_bytes)
    if used_end > ATLAS_END:
        raise ValueError("Repacked data and code exceed bank 6 storage")
    ram_chunks = []
    for index, (start, address) in enumerate(c.segments):
        end = c.segments[index + 1][0] if index + 1 < len(c.segments) else len(payload)
        limit = RAM_END if address == RAM_BASE else SIDE_END
        if address + end - start > limit:
            raise ValueError("Resident code exceeds reserved RAM")
        ram_chunks.append(dict(address=address, size=end - start,
                               source_offset=physical(payload_address) + start))
    result = bytearray(source)
    changes = []

    def edit(offset, expected, replacement, purpose):
        old = bytes.fromhex(expected) if isinstance(expected, str) else expected
        new = bytes.fromhex(replacement) if isinstance(replacement, str) else replacement
        if len(old) != len(new) or bytes(result[offset:offset + len(old)]) != old:
            raise ValueError(f"Hook mismatch: {purpose} at {offset:05X}")
        result[offset:offset + len(new)] = new
        changes.append(dict(offset=offset, size=len(new), purpose=purpose, before=old.hex(), after=new.hex()))

    def hook(offset, expected, label, purpose, opcode=0xCD):
        edit(offset, expected, bytes([opcode]) + struct.pack("<H", c.labels[label]), purpose)

    loader = Code(LOADER_ADDRESS)
    loader.emit("F3 3E 06 32 00 80 32 F2 F0", "di / ld a,6 / ld ($8000),a / ld ($F0F2),a")
    for chunk in ram_chunks:
        source_address = 0x8000 + chunk["source_offset"] - 6 * 8192
        loader.emit("21 " + struct.pack("<H", source_address).hex(" "), "ld hl,resident_code_source")
        loader.emit("11 " + struct.pack("<H", chunk["address"]).hex(" "), "ld de,resident_code_destination")
        loader.emit("01 " + struct.pack("<H", chunk["size"]).hex(" "), f"ld bc,{chunk['size']}")
        loader.emit("ED B0", "ldir")
    loader.emit("3E 02 32 00 80 32 F2 F0 FB", "ld a,2 / ld ($8000),a / ld ($F0F2),a / ei")
    loader.jp(0x5C92)
    loader_bytes = loader.finish()
    if len(loader_bytes) > 64:
        raise ValueError("Startup loader overflow")
    edit(0x00A9, "CD 92 5C", "CD C0 BF", "Install helpers after RAM and mapper initialization")
    edit(LOADER_OFFSET, bytes([255]) * len(loader_bytes), loader_bytes, "Startup loader")
    edit(physical(POSE_TABLE), source[physical(POSE_TABLE):physical(POSE_TABLE) + len(table)], table,
         "Repoint losslessly packed actor pose streams")
    storage = poses + atlas + payload + codec_bytes + bytes([255]) * (ATLAS_END - used_end)
    edit(physical(POSE_START), source[physical(POSE_START):physical(ATLAS_END)], storage,
         "Lossless graphics packing and resident code storage within bank 6")
    edit(0x14D1, "21 C8 B9", b"\xcd" + struct.pack("<H", codec.labels["image_upload"]),
         "Unpack original item/candle bytes to existing image work buffer")
    edit(0x14DC, "21 C8 BD", "21 00 EC", "Read four candle images from unpacked work buffer")
    edit(0x14E3, "05", "04", "Upload four packed candles before original fifth-image source")
    edit(0x14E4, "CD 90 4A", b"\xcd" + struct.pack("<H", codec.labels["candle_upload"]),
         "Preserve original fifth-image source and upload order")
    if fall:
        hook(0x3136, "3A 20 C4", "special_state", "Allow special weapons in natural-fall state")
        edit(0x31E9, "04", "05", "Advance attacks in state 4; keep hurt/death restrictions")
        pose = b"\xcd" + struct.pack("<H", c.labels["fall_pose"]) + b"\x00" * 7
        edit(0x2F48, "11 00 00 ED 53 2E C4 CD 5F 76", pose, "Preserve active attack poses during falling")
        hook(0x3194, "3A 61 C4", "holy_water_slot", "Guard and clear left holy-water slot")
        hook(0x31A1, "3A 61 C4", "holy_water_slot", "Guard and clear right holy-water slot")
    if edges:
        hook(0x5CF9, "C3 1D 5F", "spawn_ground", "Spawn zombies at an edge with physical floor", 0xC3)
        hook(0x5DB8, "C3 1D 5F", "spawn_flying", "Spawn periodic flying enemies at X=0/255", 0xC3)
        hook(0x59EC, "DD 7E 05", "cull_x", "Keep entering enemies and small hearts", 0xC3)
        hook(0x247E, "DD 86 05", "sprite_x", "Clip normal pose parts with early clock")
        hook(0x24B4, "DD 86 05", "sprite_shared", "Clip shared pose parts with early clock")
        integrate = b"\xc3" + struct.pack("<H", c.labels["integrate_x"]) + b"\x00" * 5
        edit(0x59DD, "19 DD 75 04 DD 74 05 C9", integrate, "Clamp small-heart X integration without wrapping")
        hook(0x5C12, "DD 7E 05", "heart_landing_x", "Keep resting small-heart sprites inside the screen")
        hook(0x5C63, "C3 98 7B", "drop_floor", "Prevent small hearts from probing the opposite edge", 0xC3)
        edit(0x5FB2, "DD 36 7F 01", b"\xcd" + struct.pack("<H", c.labels["projectile_init"]) + b"\0", "Reset linear projectile edge state")
        hook(0x34C7, "DD 86 03", "weapon_x", "Track sword X overflow")
        hook(0x34D7, "DD 7E 05", "weapon_cull", "Keep swords until all pixels leave the screen", 0xC3)
        hook(0x32CB, "C3 35 75", "weapon_draw", "Clip sword sprites; preserve other weapon drawing", 0xC3)
        hook(0x4500, "3E 06 85", "weapon_collision", "Reject sword collisions after X wraps", 0xC3)
    c.lines.extend(["; Bank 6 image decompressor and upload adapters"] + codec.lines)
    return bytes(result), dict(source_sha256=SOURCE_SHA256, rom_sha256=hashlib.sha256(result).hexdigest(),
                              rom_bytes=len(result), helper_bytes=len(payload), helper_start=RAM_BASE,
                              helper_end=RAM_BASE + ram_chunks[0]["size"], symbols=c.labels,
                              ram_chunks=ram_chunks, asset_repack=asset_info,
                              bank6_free_bytes=ATLAS_END - used_end, changes=changes), c, loader
