"""Z80 hooks for the supported 128 KiB Vampire Killer cartridge dump.

Only the exact input revision is accepted. Helpers live in E618..E7FF and
F100..F1C8, outside the game stack, image buffer and BIOS work areas.
The startup loader runs after RAM clearing and mapper initialization.
"""
from __future__ import annotations

import hashlib
import struct
from feature_catalog import CATALOG, legacy_selection, resolve_selection
from compact_assets import ATLAS_END, POSE_START, POSE_TABLE, physical, repack

SOURCE_SHA256 = "99eabaaeb2b6c02220e131043d5a6401d0d8c5f413d89204547adcc04d65e7e2"
RAM_BASE = 0xE618
RAM_END = 0xE800
SIDE_BASE = 0xF100
SIDE_END = 0xF1C9
LOADER_OFFSET = 0x7FC0
LOADER_ADDRESS = 0xBFC0
OUTPUT_SIZE = 0x20000
VARIANTS = {
    "fall_attack": (True, False, False),
    "screen_edges": (False, True, False),
    "combined": (True, True, False),
    "shield_fix": (False, False, True),
    "fall_attack_shield": (True, False, True),
    "screen_edges_shield": (False, True, True),
    "combined_shield": (True, True, True),
}


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


def selected_helpers(selected):
    c = Code(RAM_BASE)
    for fix in selected:
        if fix.emit_helpers is not None:
            fix.emit_helpers(c)
    return c


def helpers(fall, edges, shield=False):
    """Compatibility entry point for the original three-feature diagnostics."""
    c = selected_helpers(resolve_selection(legacy_selection(fall, edges, shield)))
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


def make_rom(source, *, fall, edges, shield=False):
    """Compatibility wrapper; new callers select stable feature IDs instead."""
    return make_selected_rom(source, legacy_selection(fall, edges, shield))


def make_selected_rom(source, feature_ids, *, catalog=CATALOG):
    if len(source) != OUTPUT_SIZE or hashlib.sha256(source).hexdigest() != SOURCE_SHA256:
        raise ValueError("Unsupported input ROM. Expected 128 KiB SHA-256 " + SOURCE_SHA256)
    selected = resolve_selection(feature_ids, catalog)
    if any(fix.extended_helpers for fix in selected):
        from expanded_rom import make_expanded
        return make_expanded(source, selected, catalog)
    c = selected_helpers(selected)
    payload = c.finish()
    table, poses, atlas, asset_info = repack(source)
    atlas_address = POSE_START + len(poses)
    payload_address = atlas_address + len(atlas)
    codec = image_loader(payload_address + len(payload), atlas_address)
    codec_bytes = codec.finish()
    used_end = codec.base + len(codec_bytes)
    if used_end > ATLAS_END:
        raise ValueError(f"Repacked data and code exceed bank 6 storage by {used_end - ATLAS_END} bytes")
    ram_chunks = []
    for index, (start, address) in enumerate(c.segments):
        end = c.segments[index + 1][0] if index + 1 < len(c.segments) else len(payload)
        size = end - start
        if size == 0:
            continue  # LDIR with BC=0 would copy 65536 bytes.
        if not any(begin <= address and address + size <= limit
                   for begin, limit in ((RAM_BASE, RAM_END), (SIDE_BASE, SIDE_END))):
            raise ValueError(f"Resident code exceeds reserved RAM at ${address:04X} ({size} bytes)")
        if any(address < chunk["address"] + chunk["size"] and chunk["address"] < address + size
               for chunk in ram_chunks):
            raise ValueError(f"Overlapping resident RAM segments at ${address:04X}")
        ram_chunks.append(dict(address=address, size=end - start,
                               source_offset=physical(payload_address) + start))
    result = bytearray(source)
    changes = []
    owner = "core"

    def edit(offset, expected, replacement, purpose):
        old = bytes.fromhex(expected) if isinstance(expected, str) else expected
        new = bytes.fromhex(replacement) if isinstance(replacement, str) else replacement
        if offset < 0 or offset + len(new) > len(source):
            raise ValueError(f"Out-of-range ROM edit: {owner} at {offset:05X}")
        for change in changes:
            if offset < change["offset"] + change["size"] and change["offset"] < offset + len(new):
                raise ValueError(f"Overlapping ROM edits: {change['owner']} and {owner} at {offset:05X}")
        if len(old) != len(new) or bytes(result[offset:offset + len(old)]) != old:
            raise ValueError(f"Hook mismatch: {purpose} at {offset:05X}")
        result[offset:offset + len(new)] = new
        changes.append(dict(offset=offset, size=len(new), purpose=purpose, owner=owner, before=old.hex(), after=new.hex()))

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
    for fix in selected:
        owner = fix.id
        if fix.apply is not None:
            fix.apply(edit, hook, c)
    c.lines.extend(["; Bank 6 image decompressor and upload adapters"] + codec.lines)
    return bytes(result), dict(source_sha256=SOURCE_SHA256, rom_sha256=hashlib.sha256(result).hexdigest(),
                              features={fix.id: fix in selected for fix in catalog},
                              selected_fixes=[fix.id for fix in selected],
                              rom_bytes=len(result), helper_bytes=len(payload), helper_start=RAM_BASE,
                              helper_end=next((chunk["address"] + chunk["size"] for chunk in ram_chunks
                                               if chunk["address"] == RAM_BASE), RAM_BASE), symbols=c.labels,
                              ram_chunks=ram_chunks, asset_repack=asset_info,
                              bank6_free_bytes=ATLAS_END - used_end, changes=changes), c, loader
