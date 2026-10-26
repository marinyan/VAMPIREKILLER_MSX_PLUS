"""2 Mbit code extension. Original assets stay at their original offsets."""
import hashlib
import struct

from patches import Code, RAM_BASE, RAM_END, SIDE_BASE, SIDE_END, LOADER_ADDRESS, LOADER_OFFSET, SOURCE_SHA256

OUTPUT_BYTES = 0x40000
CODE_BANK = 16
EXTRA_BASE, EXTRA_END = 0xF1C9, 0xF380


class BankedCode(Code):
    """Numeric calls enter original bank 2; label calls stay in the new bank."""
    def __init__(self, bridge):
        super().__init__(0x8000)
        self.bridge = bridge

    def call(self, target):
        if isinstance(target, int):
            super().call(self.bridge)
            self.emit(struct.pack("<HB", target, 2).hex(" "), "dw original_target / db original_bank")
        else:
            super().call(target)

    def jp(self, target):
        if isinstance(target, int):
            self.call(target)
            self.emit("C9", "ret ; original tail call after restoring the code bank")
        else:
            super().jp(target)


def emit_bridge(code):
    code.label("extension_call")
    # Three extra stack words become target, return adapter, and previous bank.
    # Saved registers are restored before entering the target, including flags.
    code.emit("E5 E5 E5 E5 D5 C5 F5", "reserve three words / push hl / push de / push bc / push af")
    code.emit("ED 57 F3 21 0D 00 39 36 00", "ld a,i / di / address saved-bank high byte / clear saved IFF")
    code.branch(0xE2, "extension_iff_saved", "jp po,")
    code.emit("34", "inc (hl) ; remember enabled caller interrupts")
    code.label("extension_iff_saved")
    code.emit("21 0E 00 39 5E 23 56 EB", "ld hl,14 / add hl,sp / read inline descriptor / ex de,hl")
    code.emit("4E 23 46 23 7E 23 EB", "read target into bc and bank into a / recover stack descriptor address")
    code.emit("72 2B 73 2B 2B 5F", "replace descriptor return with continuation / retain saved IFF byte")
    code.emit("3A F2 F0 77 7B 32 00 80 32 F2 F0", "save previous bank on stack / select requested bank")
    code.branch(0x11, "extension_return", "ld de,")
    code.emit("2B 72 2B 73 2B 70 2B 71", "write return adapter and target addresses on stack")
    code.emit("F1 C1 D1 E1 C9", "pop af / pop bc / pop de / pop hl / ret into target")
    code.label("extension_return")
    code.emit("F3 E3 F5 7D 32 00 80 32 F2 F0 CB 44", "di / ex (sp),hl / preserve result af / restore previous bank / test saved IFF")
    code.jr("extension_return_disabled", "z")
    code.emit("F1 E1 FB C9", "restore result af and hl / ei / ret")
    code.label("extension_return_disabled")
    code.emit("F1 E1 C9", "restore result af and hl / ret with caller interrupts disabled")


def make_expanded(source, selected, catalog):
    resident = Code(RAM_BASE)
    resident.enabled = {fix.id for fix in selected}
    resident.weapon_edge_offset = 13
    for fix in selected:
        if not fix.extended_helpers and fix.emit_helpers:
            fix.emit_helpers(resident)
    resident.org(EXTRA_BASE)
    emit_bridge(resident)
    extension = BankedCode(resident.labels["extension_call"])
    extension.enabled = {fix.id for fix in selected}
    extension.source = source
    for fix in selected:
        if fix.extended_helpers and fix.emit_helpers:
            fix.emit_helpers(extension)
    has_claims = bool(extension.enabled & {"weapon_owner", "axe_wall", "screen_edges"})
    if has_claims:
        from fixes.projectile_support import emit_claims
        emit_claims(extension)
    if extension.enabled & {"pause_visibility", "weapon_graphics"}:
        from fixes.display_support import emit as emit_display_support
        emit_display_support(extension)
    body = extension.finish()
    if len(body) > 8192:
        raise ValueError("Extension code exceeds one 8 KiB bank")
    result = bytearray(source) + bytearray([255]) * (OUTPUT_BYTES - len(source))
    changes, owner = [], "core"

    def entry(label):
        if label not in resident.labels:
            if label not in extension.labels:
                raise ValueError(f"Unknown extension entry: {label}")
            resident.label(label)
            resident.call("extension_call")
            resident.emit(struct.pack("<HB", extension.labels[label], CODE_BANK).hex(" "),
                          "dw extension_target / db extension_bank")
            resident.emit("C9", "ret")
        return resident.labels[label]

    def edit(offset, expected, replacement, purpose):
        old = bytes.fromhex(expected) if isinstance(expected, str) else bytes(expected)
        new = bytes.fromhex(replacement) if isinstance(replacement, str) else bytes(replacement)
        if offset < 0 or offset + len(new) > len(result):
            raise ValueError(f"Out-of-range ROM edit: {owner} at {offset:05X}")
        for previous in changes:
            if offset < previous["offset"] + previous["size"] and previous["offset"] < offset + len(new):
                raise ValueError(f"Overlapping ROM edits: {previous['owner']} and {owner} at {offset:05X}")
        if len(old) != len(new) or result[offset:offset + len(old)] != old:
            raise ValueError(f"Hook mismatch: {purpose} at {offset:05X}")
        result[offset:offset + len(new)] = new
        changes.append(dict(offset=offset, size=len(new), purpose=purpose, owner=owner,
                            before=old.hex(), after=new.hex()))

    def hook(offset, expected, label, purpose, opcode=0xCD):
        edit(offset, expected, bytes([opcode]) + struct.pack("<H", entry(label)), purpose)

    for fix in selected:
        owner = fix.id
        if fix.apply:
            fix.apply(edit, hook, resident)
    if has_claims:
        from fixes.projectile_support import apply_claims
        owner = "projectile_metadata"
        apply_claims(edit, hook)
    owner = "core"
    payload = resident.finish()
    payload_offset = CODE_BANK * 8192 + len(body)
    if len(body) + len(payload) > 8192:
        raise ValueError("Code and resident helpers exceed extension bank storage")
    chunks = []
    for index, (start, address) in enumerate(resident.segments):
        end = resident.segments[index + 1][0] if index + 1 < len(resident.segments) else len(payload)
        size = end - start
        if not size:
            continue
        if not any(begin <= address and address + size <= limit for begin, limit in
                   ((RAM_BASE, RAM_END), (SIDE_BASE, SIDE_END), (EXTRA_BASE, EXTRA_END))):
            raise ValueError(f"Resident code exceeds reserved RAM at ${address:04X} ({size} bytes)")
        if any(address < prior["address"] + prior["size"] and prior["address"] < address + size for prior in chunks):
            raise ValueError("Overlapping resident RAM segments")
        chunks.append(dict(address=address, size=size, source_offset=payload_offset + start))
    loader = Code(LOADER_ADDRESS)
    loader.emit("F3 3E 10 32 00 80 32 F2 F0", "di / select extension bank 16")
    for chunk in chunks:
        loader.emit("21 " + struct.pack("<H", 0x8000 + chunk["source_offset"] - CODE_BANK * 8192).hex(" "), "ld hl,resident_source")
        loader.emit("11 " + struct.pack("<H", chunk["address"]).hex(" "), "ld de,resident_destination")
        loader.emit("01 " + struct.pack("<H", chunk["size"]).hex(" "), "ld bc,resident_size")
        loader.emit("ED B0", "ldir")
    loader.emit("3E 02 32 00 80 32 F2 F0 FB", "restore original bank 2 / ei")
    loader.jp(0x5C92)
    loader_bytes = loader.finish()
    if len(loader_bytes) > 64:
        raise ValueError("Startup loader overflow")
    edit(0x00A9, "CD 92 5C", "CD C0 BF", "Install resident bridge after RAM and mapper initialization")
    edit(LOADER_OFFSET, bytes([255]) * len(loader_bytes), loader_bytes, "Extension startup loader")
    edit(CODE_BANK * 8192, bytes([255]) * len(body + payload), body + payload, "Additional code; no relocated game assets")
    return bytes(result), dict(source_sha256=SOURCE_SHA256, rom_sha256=hashlib.sha256(result).hexdigest(),
                              features={fix.id: fix in selected for fix in catalog},
                              selected_fixes=[fix.id for fix in selected], rom_bytes=len(result),
                              helper_bytes=len(payload), helper_start=RAM_BASE,
                              helper_end=next((v["address"] + v["size"] for v in chunks if v["address"] == RAM_BASE), RAM_BASE),
                              symbols=resident.labels, ram_chunks=chunks, asset_repack=None,
                              bank6_free_bytes=None, extension_bank=CODE_BANK, extension_code_bytes=len(body),
                              extension_free_bytes=8192 - len(body) - len(payload), changes=changes), resident, loader
