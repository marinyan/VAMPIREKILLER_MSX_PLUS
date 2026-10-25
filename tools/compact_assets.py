"""Losslessly repack bank 6 poses and the twelve 16x16 item/candle images."""
from __future__ import annotations

import hashlib
import struct

POSE_TABLE = 0xB473
POSE_START = 0xB5C3
ATLAS_START = 0xB9C8
ATLAS_END = 0xBFC8
BANK_OFFSET = 6 * 8192
TEMPLATES = {
    0x80: [(0xE0, 0xF8)] * 2 + [(0xF0, 0xF8)] * 2,
    0x81: [(0xF1, 0xF8)] * 2,
    0x82: [(0xD1, 0xF8)] * 2 + [(0xE1, 0xF8)] * 2 + [(0xF1, 0xF8)] * 2,
}


def physical(address):
    return BANK_OFFSET + address - 0xA000


def decode_pose(data):
    if data[0] in TEMPLATES:
        coordinates = TEMPLATES[data[0]]
        if len(data) != len(coordinates) + 1:
            raise ValueError("Unexpected shared pose length")
        return tuple((y, x, pattern) for (y, x), pattern in zip(coordinates, data[1:]))
    if len(data) % 3:
        raise ValueError("Unexpected ordinary pose length")
    return tuple(tuple(data[i:i + 3]) for i in range(0, len(data), 3))


def pack_poses(source):
    pointers = struct.unpack("<168H", source[physical(POSE_TABLE):physical(POSE_TABLE) + 336])
    unique = sorted(set(pointers))
    assert unique[0] == POSE_START
    encoded, originals = {}, {}
    for i, address in enumerate(unique):
        end = unique[i + 1] if i + 1 < len(unique) else ATLAS_START
        original = source[physical(address):physical(end)]
        parts = decode_pose(original)
        data = original
        for tag, coordinates in TEMPLATES.items():
            if [(y, x) for y, x, _ in parts] == coordinates:
                candidate = bytes([tag, *(pattern for _, _, pattern in parts)])
                if len(candidate) < len(data):
                    data = candidate
        assert decode_pose(data) == parts
        originals[address], encoded[address] = original, data
    packed = bytearray()
    for data in sorted(set(encoded.values()), key=lambda item: (-len(item), item)):
        if data not in packed:
            packed.extend(data)
    relocated = [POSE_START + packed.find(encoded[pointer]) for pointer in pointers]
    for pointer, new in zip(pointers, relocated):
        value = packed[new - POSE_START:new - POSE_START + len(encoded[pointer])]
        assert decode_pose(value) == decode_pose(originals[pointer])
    return struct.pack("<168H", *relocated), bytes(packed), dict(
        poses=168, original_bytes=ATLAS_START - POSE_START, packed_bytes=len(packed),
        all_decoded_parts_equal=True)


def pack_lz(data):
    """Optimal parse for literal runs and 1..256-byte backward copies."""
    size = len(data)
    costs, choices = [0] * (size + 1), {}
    costs[size] = 1  # zero terminator
    for position in range(size - 1, -1, -1):
        best = min((1 + n + costs[position + n], 0, n)
                   for n in range(1, min(127, size - position) + 1))
        longest, distance = 0, 0
        for back in range(1, min(256, position) + 1):
            length = 0
            while length < min(130, size - position) and data[position + length] == data[position + length - back]:
                length += 1
            if length > longest:
                longest, distance = length, back
        for length in range(3, longest + 1):
            candidate = (2 + costs[position + length], distance, length)
            if candidate < best:
                best = candidate
        costs[position] = best[0]
        choices[position] = best[1:]
    packed, position = bytearray(), 0
    while position < size:
        back, length = choices[position]
        if back:
            packed.extend((128 + length - 3, back - 1))
        else:
            packed.append(length)
            packed.extend(data[position:position + length])
        position += length
    packed.append(0)
    assert len(packed) == costs[0]
    assert unpack_lz(packed) == data
    return bytes(packed)


def unpack_lz(packed):
    result, position = bytearray(), 0
    while packed[position]:
        control = packed[position]
        position += 1
        if control < 128:
            result.extend(packed[position:position + control])
            position += control
        else:
            length, back = (control & 127) + 3, packed[position] + 1
            position += 1
            if back > len(result):
                raise ValueError("Invalid backward distance")
            for _ in range(length):
                result.append(result[-back])
    return bytes(result)


def repack(source):
    table, poses, pose_info = pack_poses(source)
    atlas = source[physical(ATLAS_START):physical(ATLAS_END)]
    compressed = pack_lz(atlas)
    return table, poses, compressed, dict(
        poses=pose_info, atlas_bytes=len(atlas), compressed_atlas_bytes=len(compressed),
        atlas_sha256=hashlib.sha256(atlas).hexdigest(), all_atlas_bytes_equal=unpack_lz(compressed) == atlas)
