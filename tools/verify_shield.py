"""Check shield lifetime, area entry, and equipment removal in original Z80 code.

These arranged function tests execute the cartridge routines. Rendering and
sound calls are intercepted; segment exits stop before unrelated area loading
or player knockback. They are separate from the ordinary-input campaign test.
"""
from pathlib import Path
import argparse
import hashlib
import json

from patches import VARIANTS, make_rom
from verify_emulator import run, tcl_script, read_rows

ROOT = Path(__file__).resolve().parents[1]


def fixtures():
    result = []

    def add(group, inventory, remaining, steps, *, facing=0, enemy_x=160, shots=0, item=0):
        p = bytearray(80)
        p[5], p[7], p[12], p[33] = 128, 128, facing, remaining
        actor = bytearray(128)
        actor[0], actor[3], actor[5] = 1, 128, enemy_x
        result.append(dict(name=f"{group}-{len(result)}", group=group, player=p.hex(),
                           memory={0xC701: inventory, 0xC800: actor.hex()}, steps=steps,
                           registers={"IX": 0xC800}, tiles=[],
                           metadata=dict(inventory=inventory, remaining=remaining, facing=facing,
                                         enemy_x=enemy_x, shots=shots, item=item)))

    def bullets(count, facing):
        raw = bytearray(1024)
        for n in range(count):
            raw[n * 128] = 1
            raw[n * 128 + 3] = 112
            raw[n * 128 + 5] = 120 if facing else 136
        return {0xD700: raw.hex(), 0xC425: 128, 0xC427: 128, 0xC42C: facing}

    values = (*range(17), 255)
    for inventory in (1, 0x11, 0x21, 0x31, 0xA9):
        for remaining in values:
            add("shield_transition", inventory, remaining, [(0x62EC, {}, {})])
    for inventory in (0x11, 0x21, 0xB1):
        for remaining in values:
            add("shield_boss_clear", inventory, remaining, [(0x70DC, {}, {}), (0x62EC, {}, {})])
    for item in (3, 4):
        for inventory in (1, 0x11, 0x21, 0x31, 0x8F):
            for remaining in (0, 1, 7, 16, 255):
                add("shield_acquire", inventory, remaining, [(0x8D30, {}, {"AF": item << 8})], item=item)
    for inventory in (1, 0x11, 0x21, 0x31):
        for remaining in (0, 1, 2, 7, 16, 255):
            for facing in (0, 1):
                for enemy_x in (96, 160):
                    add("shield_contact", inventory, remaining, [(0x816C, {}, {})],
                        facing=facing, enemy_x=enemy_x)
    for inventory in (1, 0x11, 0x21, 0x31, 0xA1):
        for remaining in (0, 1, 2, 7, 16, 255):
            for shots in (1, 2, 8):
                for facing in (0, 1):
                    add("shield_projectiles", inventory, remaining, [(0x8610, bullets(shots, facing), {})],
                        facing=facing, shots=shots)
    for inventory in (0x11, 0x21):
        for remaining in (1, 7, 16):
            if inventory & 0x10:
                step = (0x816C, {0xC425: 128, 0xC427: 128}, {})
            else:
                step = (0x8610, bullets(1, 0), {})
            add("shield_transition_hit", inventory, remaining, [(0x62EC, {}, {}), step], shots=1)
    for facing in (0, 1):
        steps = [(0x8D30, {}, {"AF": 4 << 8})]
        for n in range(20):
            if n in (5, 12):
                steps.append((0x62EC, {}, {}))
            steps.append((0x8610, bullets(1, facing), {}))
        add("shield_lifetime", 1, 0, steps, facing=facing)
    return result


def script_for(cases, output):
    script = tcl_script(cases, output)
    script = script.replace(
        '[binary encode hex [debug read_block memory 0xd460 64]]"',
        '[binary encode hex [debug read_block memory 0xd460 64]]\t'
        '[binary encode hex [debug read_block memory 0xc700 32]]\t[reg BC]"')
    # Return at the real segment boundaries, preserving the tested call's stack.
    script = script.replace('debug set_bp 0xf200 {} returned', '''debug set_bp 0xf200 {} returned
 debug set_bp 0x62ef {$::active} return_now
 debug set_bp 0x81a8 {$::active} return_now
 debug set_bp 0x8ee6 {$::active} return_now''')
    return script


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--openmsx", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=ROOT / "build/shield-verification")
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    source = args.rom.read_bytes()
    cases = fixtures()
    hashes, checks = {}, {}
    base_damage = source[0x41CF]
    baseline_bug = False
    for name, flags in {"original": (False, False, False), **VARIANTS}.items():
        fixed = flags[2]
        rom = source if name == "original" else make_rom(source, fall=flags[0], edges=flags[1], shield=fixed)[0]
        path, output = out / f"{name}.rom", out / f"{name}.tsv"
        path.write_bytes(rom)
        run(args.openmsx.resolve(), path, script_for(cases, output), out, name)
        rows, _ = read_rows(output, cases)
        extra = {}
        for line in output.read_text().splitlines():
            parts = line.split("\t")
            if parts[0].isdigit():
                extra[int(parts[0]), int(parts[1])] = (bytes.fromhex(parts[12]), int(parts[13]) >> 8)
        for ci, case in enumerate(cases):
            m, group = case["metadata"], case["group"]
            last = len(case["steps"]) - 1
            p, status, actors, _, _, _, _, shots, _, _ = rows[ci, last]
            inventory, damage = extra[ci, last]
            inv, remaining = m["inventory"], m["remaining"]
            if group == "shield_transition":
                expected = bytearray(80)
                if fixed:
                    expected[33] = remaining
                assert p == expected, (name, case["name"], p.hex())
                assert inventory[1] == (inv & 0xCF if fixed and not remaining else inv)
            elif group == "shield_boss_clear":
                assert p == bytes(80) and inventory[1] == (inv & 0x80), (name, case["name"])
                assert status[6] == 0
            elif group == "shield_acquire":
                owned, other = (0x10, 0x20) if m["item"] == 3 else (0x20, 0x10)
                assert p[33] == 16 and inventory[1] == ((inv & ~other) | owned), (name, case["name"])
            elif group == "shield_contact":
                active = inv & 0x10 and (m["facing"] == int(m["enemy_x"] < 128))
                if fixed and not remaining:
                    inv &= 0xCF
                    active = False
                if active:
                    remaining = (remaining - 1) & 255
                    if remaining == 0:
                        inv &= ~0x10
                assert p[33] == remaining and inventory[1] == inv, (name, case["name"])
                assert damage == base_damage * (1 if active else 2), (name, case["name"], damage)
            elif group == "shield_projectiles":
                if fixed and not remaining:
                    inv &= 0xCF
                blocked = min(remaining, m["shots"]) if fixed and inv & 0x20 else m["shots"] if inv & 0x20 else 0
                for n in range(blocked):
                    remaining = (remaining - 1) & 255
                    if remaining == 0:
                        inv &= ~0x20
                assert p[33] == remaining and inventory[1] == inv, (name, case["name"], p[33], remaining)
                # Blocked shots become the original type12 disappearance effect.
                assert sum(shots[n * 128] != 1 for n in range(m["shots"])) == blocked, (name, case["name"])
            elif group == "shield_transition_hit":
                if fixed:
                    assert p[33] == m["remaining"] - 1
                else:
                    assert p[33] == 255
                    if name == "original":
                        baseline_bug = True
            elif group == "shield_lifetime":
                if fixed:
                    assert p[33] == 0 and inventory[1] == 1, (name, case["name"])
                    uses = 0
                    for si, step in enumerate(case["steps"]):
                        if step[0] == 0x8610:
                            uses += 1
                            actual = rows[ci, si]
                            assert actual[0][33] == max(0, 16 - uses)
                            assert (actual[7][0] != 1) == (uses <= 16)
            else:
                raise AssertionError(group)
        hashes[name] = hashlib.sha256(rom).hexdigest()
        checks[name] = dict(cases=len(cases), function_returns=len(rows), shield_fix=fixed)
        print(f"PASS {name}: {len(cases)} shield cases, {len(rows)} function returns", flush=True)
    assert baseline_bug
    report = dict(status="passed", kind="arranged Z80 shield function diagnostics",
                  original_zero_to_255_bug_reproduced=baseline_bug, rom_sha256=hashes, checks=checks,
                  contracts=["remaining durability survives ordinary area entry", "boss/death equipment reset removes shields and durability",
                             "both shield pickups grant 16 uses", "zero durability never underflows in fixed variants",
                             "a breaking projectile shield stops blocking the rest of the same pass"],
                  limitations=["rendering and sound calls intercepted", "not an ordinary-input campaign or hardware test"])
    (out / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
