"""Run original Z80 routines and all patched ROM combinations in openMSX.

These are arranged RAM/register function tests, plus a boot/input smoke test.
No ROM code is replaced at runtime. Sound and IRQ entry are intercepted during
function tests to keep asynchronous main-loop updates out of the fixtures.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import subprocess

from patches import VARIANTS, RAM_BASE, RAM_END, SIDE_BASE, SIDE_END, make_rom

ROOT = Path(__file__).resolve().parents[1]


def cases():
    result = []

    def add(name, group, player=None, memory=None, steps=None, registers=None, metadata=None, tiles=None):
        result.append(dict(name=name, group=group, player=bytes(player or [0] * 80).hex(),
                           memory=memory or {}, steps=steps or [(0x710D, {}, {})],
                           registers=registers or {}, metadata=metadata or {}, tiles=tiles or []))

    for weapon in range(5):
        for facing in (0, 1):
            p = [0] * 80
            p[0], p[5], p[7], p[12] = 4, 96, 100, facing
            p[4], p[6] = 37, 219
            steps = []
            for tick in range(20):
                steps.extend([(0x6B39, {0xC003: tick, 0xC006: 16 if tick == 0 else 0}, {}), (0x710D, {}, {})])
            add(f"fall-{weapon}-{facing}", "trajectory", p, {0xC416: weapon}, steps,
                metadata=dict(weapon=weapon, facing=facing))

    for state in range(8):
        for weapon in range(5):
            p = [0] * 80
            p[0], p[5], p[7], p[2], p[9], p[22], p[48] = state, 128, 128, 1, 1, weapon, 1
            add(f"attack-state-{state}-{weapon}", "attack_state", p, metadata=dict(state=state, weapon=weapon),
                steps=[(0x71E0, {}, {})])

    for state in (0, 1, 2, 3, 4, 5, 6, 7):
        for special, inventory, pressed in (("water-left", 8, 4), ("water-right", 8, 8), ("clock", 64, 2)):
            for hearts in (0x04, 0x05, 0x10, 0x99):
                p = [0] * 80
                p[0], p[5], p[7] = state, 128, 128
                add(f"special-{state}-{special}-{hearts}", "special", p,
                    {0xC701: inventory, 0xC006: pressed, 0xC417: hearts},
                    metadata=dict(state=state, special=special, hearts=hearts))

    for state in (1, 4):
        for pressed in (4, 8):
            for phase in (0, 1, 2, 3, 4):
                for slot0_pending in (False, True):
                    p = [0] * 80
                    p[0], p[5], p[7], p[2], p[22] = state, 128, 128, phase, 2
                    p[48], p[49], p[64] = (1 if slot0_pending else 2), (0 if slot0_pending else 2), 1
                    p[66:80] = [0x55] * 14
                    add(f"ownership-{state}-{pressed}-{phase}-{slot0_pending}", "ownership", p,
                        {0xC701: 8, 0xC006: pressed}, steps=[(0x7116, {}, {})],
                        metadata=dict(state=state, phase=phase, pending0=slot0_pending, direction=pressed))

    for kind in range(1, 47):
        for x in (0, 1, 6, 7, 16, 128, 240, 241, 254, 255):
            for vx in (0x0200, 0xFE00):
                raw = bytearray(128)
                raw[0], raw[3], raw[5], raw[6] = kind, 192, x, 1
                raw[9:11] = vx.to_bytes(2, "little")
                add(f"cull-{kind}-{x}-{vx}", "cull", memory={0xC800: raw.hex()},
                    steps=[(0x99E5, {}, {})], registers={"IX": 0xC800},
                    metadata=dict(kind=kind, x=x, vx=vx))

    for kind in (1, 4, 7, 8, 0x24):
        for x in (0, 1, 4, 7, 8, 9, 128, 240, 248, 255):
            add(f"sprite-{kind}-{x}", "sprite", steps=[(0x5F1D, {}, {"BC": kind, "DE": x * 256 + 160}),
                                                         (0x6445, {}, {}), (0x64EC, {}, {})],
                metadata=dict(kind=kind, x=x))

    for kind in (1, 4, 7, 8):
        for x in (16, 240):
            for floor in (0, 1):
                add(f"spawn-{kind}-{x}-{floor}", "spawn",
                    steps=[(0x9CF9 if kind == 1 else 0x9DB8, {}, {"BC": kind, "DE": x * 256 + 192})],
                    tiles=[(0, 192, floor), (248, 192, floor)],
                    metadata=dict(kind=kind, x=x, floor=floor))

    for kind in (1, 4, 0x24):
        for x in (0, 1, 255, 256, 512, 0x7FFF, 0xF7FF, 0xF800, 0xF801, 0xFEFF, 0xFFFF):
            for vx in (0xF800, 0xFE00, 0xFFFF, 0, 1, 0x0200, 0x0800):
                raw = bytearray(128)
                raw[0], raw[6] = kind, 1
                raw[2:4] = (0x8025).to_bytes(2, "little")
                raw[4:6] = x.to_bytes(2, "little")
                raw[7:9] = (0x0080).to_bytes(2, "little")
                raw[9:11] = vx.to_bytes(2, "little")
                add(f"integrate-{kind}-{x}-{vx}", "integrate", memory={0xC800: raw.hex()},
                    steps=[(0x99B9, {}, {})], registers={"IX": 0xC800},
                    metadata=dict(kind=kind, x=x, vx=vx))

    for x in (0, 1, 4, 7, 8, 16, 128, 239, 240, 247, 248, 255):
        add(f"landing-{x}", "landing",
            steps=[(0x5F1D, {}, {"BC": 0x24, "DE": x * 256 + 192}), (0x9BD9, {}, {})],
            metadata=dict(x=x))
    for x in (0, 1, 7, 8, 9, 10):
        raw = bytearray(128)
        raw[0], raw[3], raw[5] = 0x24, 128, x
        add(f"floor-{x}", "floor", memory={0xC800: raw.hex()},
            steps=[(0x9C5D, {}, {})], registers={"IX": 0xC800},
            tiles=[(248, 128, 1), (240, 128, 1)], metadata=dict(x=x))
    for kind in range(1, 13):
        for x in (0, 4, 7, 128, 240, 248, 255):
            for vx in (0x0300, 0xFD00):
                raw = bytearray(128)
                raw[0], raw[3], raw[5], raw[6], raw[11], raw[14] = kind, 128, x, 1, 3, 3
                raw[9:11] = vx.to_bytes(2, "little")
                raw[32], raw[33], raw[38], raw[37], raw[42] = 2, 16, 17, 2, 76
                steps = []
                for tick in range(8):
                    steps.extend([(0x99B9, {}, {"IX": 0xD700}), (0x99E5, {}, {}),
                                  (0x6445, {}, {}), (0x64E5, {}, {})])
                add(f"bullet-{kind}-{x}-{vx}", "bullet", memory={0xD700: raw.hex()}, steps=steps,
                    metadata=dict(kind=kind, x=x, vx=vx))
    for kind in (2, 3, 4, 5):
        for x in (16, 128, 240):
            for speed in (5, 251):
                p = [0] * 80
                p[5], p[7] = 160, 128
                p[48:57] = [2, kind, 0, speed, 144, x, 24, 0, int(speed > 127)]
                add(f"weapon-{kind}-{x}-{speed}", "weapon_sequence", p, {0xC416: kind},
                    steps=[(0x72B2, {0xC003: tick}, {}) for tick in range(64)],
                    metadata=dict(kind=kind, x=x, speed=speed))
    for kind in (2, 3, 4, 5):
        for flag in (0, 1):
            for x in (0, 4, 128, 252, 255):
                p = [0] * 80
                p[48:64] = [2, kind, 0, 251, 128, x, 24, 0, 1, 0, 0, 0, 0, 0, 0, flag]
                add(f"weapon-collision-{kind}-{flag}-{x}", "weapon_collision", p,
                    steps=[(0x8500, {}, {"IY": 0xC450, "DE": x * 256 + 128, "HL": 0x1008})],
                    metadata=dict(kind=kind, flag=flag, x=x))
    return result


def tcl_script(fixtures, output):
    def writes(memory):
        return " ".join(f"{{{address} {'hex ' + value if isinstance(value, str) else 'byte ' + str(value)}}}"
                        for address, value in memory.items())

    def registers(values):
        return " ".join(f"{key} {value}" for key, value in values.items())

    encoded = []
    for f in fixtures:
        encoded.append("{" + f"{f['player']} {{{writes(f['memory'])}}} {{{registers(f['registers'])}}} " +
                       "{" + " ".join("{" + f"{address} {{{writes(memory)}}} {{{registers(regs)}}}" + "}"
                                       for address, memory, regs in f["steps"]) + "} " +
                       "{" + " ".join(f"{{{x} {y} {v}}}" for x, y, v in f["tiles"]) + "} " + f["group"] + "}")
    return r'''
set renderer none
set throttle off
set sound_driver null
set save_settings_on_exit false
set power on
set pause off
set active 0
set ci -1
set si -1
set fixtures {FIXTURES}
set output [open {OUTPUT} w]
fconfigure $output -buffering line
proc putmem {entries} {
 foreach entry $entries {
  lassign $entry address mode value
  if {$mode eq "hex"} {debug write_block memory $address [binary decode hex $value]} else {debug write memory $address $value}
 }
}
proc putregs {entries} {foreach {name value} $entries {reg $name $value}}
proc zero {address size} {debug write_block memory $address [binary format H* [string repeat 00 $size]]}
proc return_now {} {
 set sp [reg SP]
 set target [peek16 $sp]
 reg SP [expr {$sp+2}]
 reg IFF 0
 if {$target == 0xf200} {returned} else {reg PC $target}
}
proc nextstep {} {
 global fixtures ci si active output
 incr si
 set cfg [lindex $fixtures $ci]
 set steps [lindex $cfg 3]
 if {$si >= [llength $steps]} {nextcase;return}
 lassign [lindex $steps $si] address memory regs
 putmem $memory
 putregs $regs
 reg IFF 0
 debug write memory 0xf0d0 0
 debug write memory 0xf0d1 0xf2
 reg SP 0xf0d0
 reg PC $address
}
proc nextcase {} {
 global fixtures ci si active output
 incr ci
 if {$ci >= [llength $fixtures]} {
  puts $output "DONE\t$ci"
  close $output
  exit
 }
 set cfg [lindex $fixtures $ci]
 set si -1
 if {[lindex $cfg 5] eq "asset_vram"} {debug write_block VRAM 0 [binary decode hex [string repeat 5a 131072]]}
 # Do not inherit lives, inactive SAT coordinates or colors from the boot's RNG.
 foreach {a n} {0xc410 16 0xc420 80 0xc470 256 0xc500 128 0xc800 896 0xce00 128 0xc700 32 0xcf00 256 0xd100 768 0xc598 14 0xd700 1024 0xd400 512 0xd600 128} {zero $a $n}
 for {set n 0} {$n<18} {incr n} {debug write memory [expr {0xd638+4*$n}] 224}
 debug write_block memory 0xd3c0 [binary decode hex [string repeat 01 32]]
 debug write_block memory 0xc420 [binary decode hex [lindex $cfg 0]]
 foreach {a v} {0xc00f 0 0xc000 5 0xc001 0 0xc003 0 0xc006 0 0xc007 0 0xc002 64 0xc413 1 0xc415 32 0xc416 0 0xc417 48 0xc418 0 0xc419 0 0xc41e 255 0xc41f 255 0xc5ac 0 0xd000 0 0xd001 0 0xd002 0 0xd010 0 0xd012 0 0xc701 0} {debug write memory $a $v}
 foreach tile [lindex $cfg 4] {
  lassign $tile x y v
  debug write memory [expr {0xd100+((($y-16)/8)*32)+($x/8)}] $v
 }
 reg BC 0
 reg DE 0
 reg HL 0
 reg IX 0xc800
 putmem [lindex $cfg 1]
 putregs [lindex $cfg 2]
 if {[lindex $cfg 5] eq "asset_vram"} {
  # The original fifth candle upload reads 56 ROM padding bytes and 72 bytes
  # from C000. Give both ROMs the same explicit input for that incidental data.
  debug write_block memory 0xc000 [binary decode hex [string repeat 00 72]]
 }
 debug write memory 0x8000 2
 debug write memory 0xa000 3
 debug write memory 0xf0f2 2
 debug write memory 0xf0f3 3
 nextstep
}
proc returned {} {
 global ci si output fixtures
 if {[reg SP] != 0xf0d2} {error "unbalanced stack: [reg SP]"}
 puts $output "$ci\t$si\t[binary encode hex [debug read_block memory 0xc420 80]]\t[binary encode hex [debug read_block memory 0xc410 16]]\t[binary encode hex [debug read_block memory 0xc800 896]]\t[binary encode hex [debug read_block memory 0xd638 72]]\t[binary encode hex [debug read_block memory 0xd4e0 288]]\t[binary encode hex [debug read_block memory 0xc500 128]]\t[reg AF]\t[binary encode hex [debug read_block memory 0xd700 1024]]\t[binary encode hex [debug read_block memory 0xd618 16]]\t[binary encode hex [debug read_block memory 0xd460 64]]"
 if {[lindex [lindex $fixtures $ci] 5] eq "asset_vram"} {save_debuggable VRAM {VRAM_OUTPUT}}
 nextstep
}
proc begin {} {
 global active output
 set active 1
 puts $output "HELPERS\t[binary encode hex [debug read_block memory 0xe618 488]][binary encode hex [debug read_block memory 0xf100 201]]"
 debug set_bp 0xf200 {} returned
 debug set_bp 0x509f {$::active} return_now
 debug set_bp 0x0038 {$::active} return_now
 debug set_bp 0x414d {$::active} return_now
 nextcase
}
after time 13 {keymatrixdown 8 1}
after time 13.5 {keymatrixup 8 1}
after time 24 begin
after realtime 50 {puts $output "TIMEOUT\t$ci\t$si\t[reg PC]";close $output;exit}
'''.replace("FIXTURES", "\n".join(encoded)).replace("VRAM_OUTPUT", output.with_suffix(".vram").as_posix()).replace("OUTPUT", output.as_posix())


def run(openmsx, rom, script, outdir, name):
    script_path = outdir / f"{name}.tcl"
    script_path.write_text(script, encoding="utf-8")
    user = outdir / f"{name}-user"
    user.mkdir(exist_ok=True)
    relative = lambda p: os.path.relpath(p, ROOT)
    env = dict(os.environ, OPENMSX_SYSTEM_DATA=relative(openmsx.parent / "share"), OPENMSX_USER_DATA=relative(user))
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = 0
    with (outdir / f"{name}.log").open("wb") as log:
        subprocess.run([relative(openmsx), "-machine", "C-BIOS_MSX2_JP", "-cart", relative(rom),
                        "-romtype", "Konami", "-script", relative(script_path)], cwd=ROOT, env=env,
                       stdout=log, stderr=log, stdin=subprocess.DEVNULL, timeout=60,
                       startupinfo=startup, creationflags=0x08000000, check=True)


def read_rows(path, fixtures):
    rows, helpers, done = {}, None, False
    for line in path.read_text().splitlines():
        parts = line.split("\t")
        if parts[0] == "HELPERS":
            helpers = bytes.fromhex(parts[1])
        elif parts[0] == "DONE":
            done = int(parts[1]) == len(fixtures)
        elif parts[0] == "TIMEOUT":
            raise AssertionError(f"Emulator timeout: {parts}")
        elif parts[0] == "EVENT":
            continue
        else:
            ci, si = map(int, parts[:2])
            rows[ci, si] = [bytes.fromhex(x) for x in parts[2:8]] + [int(parts[8])] + [bytes.fromhex(x) for x in parts[9:12]]
    assert done and len(rows) == sum(len(f["steps"]) for f in fixtures), f"Incomplete capture: {path}"
    return rows, helpers


def verify(fixtures, captures):
    counts = {}
    for name, flags in {"original": (False, False, False), **VARIANTS}.items():
        rows, _ = captures[name]
        baseline = captures["original"][0]
        fall, edges, shield = flags
        checks = 0
        for ci, f in enumerate(fixtures):
            m, group = f["metadata"], f["group"]
            last = len(f["steps"]) - 1
            p, status, actors, sprites, colors, drops, af, bullets, weapon_sat, weapon_colors = rows[ci, last]
            old = baseline[ci, last]
            if group == "trajectory":
                for si in range(last + 1):
                    actual, original = rows[ci, si][0], baseline[ci, si][0]
                    # State/substate, full X/Y fractions, fall index, carried platform.
                    for start, end in ((0, 2), (4, 9), (25, 26)):
                        assert actual[start:end] == original[start:end], (name, f["name"], si, start)
                    if not fall:
                        assert actual == original, (name, f["name"], si)
                if fall:
                    assert any(rows[ci, si][0][2] != baseline[ci, si][0][2]
                               for si in range(last + 1)), (name, f["name"], "no fall attack")
            elif group == "attack_state":
                if not fall or m["state"] != 4:
                    assert p == old[0], (name, f["name"])
                else:
                    assert p[2] == 2, (name, f["name"], p.hex())
            elif group == "special":
                allowed = m["state"] == 1 or (fall and m["state"] == 4)
                accepted = allowed and m["hearts"] >= 5
                assert (status[7] != m["hearts"]) == accepted, (name, f["name"], status.hex())
                if not fall or m["state"] != 4:
                    assert p == old[0] and status == old[1], (name, f["name"])
            elif group == "ownership":
                if fall and m["state"] in (1, 4):
                    accepted = m["phase"] == 0 or m["pending0"]
                    assert (p[65] == 5) == accepted, (name, f["name"], p.hex())
                    assert status[7] == (0x25 if accepted else 0x30), (name, f["name"])
                    if accepted:
                        expected = bytearray(16)
                        expected[1], expected[8] = 5, int(m["direction"] == 4)
                        assert p[64:80] == expected, (name, f["name"], p[64:80].hex())
                else:
                    assert p == old[0] and status == old[1], (name, f["name"])
            elif group == "cull":
                if edges and m["kind"] == 0x24:
                    alive = True
                elif edges and m["kind"] in (1, 4, 7, 8):
                    alive = 7 <= m["x"] < 241 or (m["x"] < 7 and m["vx"] < 0x8000) or (m["x"] >= 241 and m["vx"] >= 0x8000)
                else:
                    alive = 7 <= m["x"] < 241
                assert (actors[0] != 0) == alive, (name, f["name"])
                if not edges or m["kind"] not in (1, 4, 7, 8, 0x24):
                    assert actors == old[2], (name, f["name"])
            elif group == "sprite":
                n = actors[32]
                assert n > 0, (name, f["name"])
                for part in range(n):
                    off = 33 + part * 5
                    slot = actors[off]
                    sat_x = sprites[slot * 4 + 1]
                    color = colors[slot * 16]
                    actual_x = sat_x - (32 if color & 128 else 0)
                    if edges:
                        reference = next(k for k, entry in enumerate(fixtures) if entry["group"] == "sprite" and entry["metadata"] == dict(kind=m["kind"], x=128))
                        offset = baseline[reference, 2][3][slot * 4 + 1] - 128
                        assert actual_x == m["x"] + offset, (name, f["name"], part, actual_x, color, offset)
                    else:
                        assert actors == old[2] and sprites == old[3], (name, f["name"])
            elif group == "spawn":
                assert actors[0] == m["kind"], (name, f["name"])
                x = (0 if m["x"] < 128 else 255) if edges and (m["kind"] != 1 or m["floor"]) else m["x"]
                assert actors[5] == x, (name, f["name"], actors[:16].hex())
            elif group == "integrate":
                vx = m["vx"] if m["vx"] < 32768 else m["vx"] - 65536
                x = min(0xF800, max(0, m["x"] + vx)) if edges and m["kind"] == 0x24 else (m["x"] + vx) & 65535
                assert int.from_bytes(actors[4:6], "little") == x, (name, f["name"], actors[:16].hex())
                assert int.from_bytes(actors[2:4], "little") == 0x80A5, (name, f["name"])
            elif group == "landing":
                assert actors[0] == 0 and drops[0] != 0, (name, f["name"], drops[:16].hex())
                assert drops[2] == (min(m["x"], 240) if edges else m["x"]) & 248, (name, f["name"], drops.hex())
            elif group == "floor":
                expected = not edges and m["x"] < 10
                assert bool(af & 1) == expected, (name, f["name"], af)
            elif group == "bullet":
                selected = edges and m["kind"] in (1, 2, 3, 5, 10, 11)
                vx = m["vx"] if m["vx"] < 32768 else m["vx"] - 65536
                alive = True
                x = m["x"] * 256
                for tick in range(8):
                    if not alive:
                        break
                    x += vx
                    expected_alive = -8 * 256 < x < 264 * 256 if selected else 7 * 256 <= (x & 65535) < 241 * 256
                    r = rows[ci, tick * 4 + 1][7]
                    assert (r[0] != 0) == expected_alive, (name, f["name"], tick, r[:32].hex(), x)
                    if selected and expected_alive:
                        if not 0 <= x < 65536:
                            assert r[14] == 0 and r[125] == 1, (name, f["name"], tick)
                        drawn = rows[ci, tick * 4 + 3]
                        sx = drawn[3][16 * 4 + 1]
                        sy = drawn[3][16 * 4]
                        col = drawn[4][16 * 16]
                        if sy != 224:
                            actual = sx - (32 if col & 128 else 0)
                            assert actual == x // 256 - 8, (name, f["name"], tick, actual, x)
                    elif not selected:
                        assert r == baseline[ci, tick * 4 + 1][7], (name, f["name"], tick)
                    alive = expected_alive
            elif group == "weapon_sequence":
                if not edges or m["kind"] != 2:
                    for si in range(last + 1):
                        actual, original = rows[ci, si], baseline[ci, si]
                        assert actual[0] == original[0] and actual[8:] == original[8:], (name, f["name"], si)
                else:
                    speed = m["speed"] if m["speed"] < 128 else m["speed"] - 256
                    x = m["x"]
                    for si in range(last + 1):
                        x += speed
                        current = rows[ci, si]
                        alive = -8 < x < 264
                        assert bool(current[0][49]) == alive, (name, f["name"], si, x)
                        if not alive:
                            assert current[8][0] == current[8][4] == 224, (name, f["name"], "stale SAT")
                            break
                        actual_x = current[8][1] - (32 if current[9][0] & 128 else 0)
                        assert actual_x == x - 8, (name, f["name"], si, actual_x, x)
            elif group == "weapon_collision":
                if edges and m["kind"] == 2 and m["flag"]:
                    assert not (af & 1), (name, f["name"], "wrapped hit")
                else:
                    assert bool(af & 1) == bool(old[6] & 1), (name, f["name"])
            checks += 1
        counts[name] = checks
    return counts


def smoke_test(openmsx, source, outdir):
    results = {}
    for name, flags in VARIANTS.items():
        rom, info, _, _ = make_rom(source, fall=flags[0], edges=flags[1], shield=flags[2])
        rompath = outdir / f"{name}.rom"
        rompath.write_bytes(rom)
        output = outdir / f"{name}-smoke.tsv"
        script = r'''
set renderer none
set throttle off
set sound_driver null
set save_settings_on_exit false
set power on
set pause off
set output [open {OUTPUT} w]
set vk_smoke_samples 0
proc vk_smoke_sample {} {
 global vk_smoke_samples output
 puts $output "[machine_info time]\t[binary encode hex [debug read_block memory 0xc000 4]]\t[binary encode hex [debug read_block memory 0xd000 4]]\t[binary encode hex [debug read_block memory 0xc420 16]]\tREAD_HELPERS"
 incr vk_smoke_samples
 if {$vk_smoke_samples<82} {after time 0.5 vk_smoke_sample} else {close $output;exit}
}
after time 13 {keymatrixdown 8 1}
after time 13.5 {keymatrixup 8 1}
after time 23 vk_smoke_sample
after time 23.5 {keymatrixdown 8 0x80}
after time 25 {keymatrixdown 8 1}
after time 25.2 {keymatrixup 8 1}
after time 28 {keymatrixdown 8 0x20}
after time 28.15 {keymatrixup 8 0x20}
after time 35 {keymatrixdown 8 1}
after time 35.2 {keymatrixup 8 1}
after time 45 {keymatrixdown 8 0x20}
after time 45.15 {keymatrixup 8 0x20}
after time 50 {keymatrixdown 8 1}
after time 50.2 {keymatrixup 8 1}
after realtime 30 {close $output;exit}
'''.replace("OUTPUT", output.as_posix()).replace("READ_HELPERS", "".join(
            f"[binary encode hex [debug read_block memory {chunk['address']} {chunk['size']}]]"
            for chunk in info["ram_chunks"]))
        run(openmsx, rompath.resolve(), script, outdir, name + "-smoke")
        samples = [line.split("\t") for line in output.read_text().splitlines()]
        assert len(samples) == 82, (name, "smoke timeout")
        helper = b"".join(rom[chunk["source_offset"]:chunk["source_offset"] + chunk["size"]]
                           for chunk in info["ram_chunks"]).hex()
        assert all(s[4] == helper for s in samples), (name, "resident code overwritten")
        gameplay = [s for s in samples if bytes.fromhex(s[1])[0] == 5]
        rooms = sorted({tuple(bytes.fromhex(s[2])[:2]) for s in gameplay})
        assert len(gameplay) >= 20 and len(rooms) >= 2, (name, "no ordinary room transition", rooms)
        results[name] = dict(samples=len(samples), gameplay_samples=len(gameplay), visited_area_rooms=rooms,
                             resident_code_unchanged=True, scope="power-on and ordinary keyboard input, 63.5 emulated seconds")
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--openmsx", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "verification")
    parser.add_argument("--reuse", action="store_true")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    source = args.rom.read_bytes()
    fixtures = cases()
    (args.out / "cases.json").write_text(json.dumps(fixtures, indent=2), encoding="utf-8")
    captures = {}
    hashes = {}
    for name in ("original", *VARIANTS):
        expected_helpers = None
        if name == "original":
            rom = source
        else:
            fall, edges, shield = VARIANTS[name]
            rom, info, _, _ = make_rom(source, fall=fall, edges=edges, shield=shield)
            expected_helpers = [(chunk, rom[chunk["source_offset"]:chunk["source_offset"] + chunk["size"]])
                                for chunk in info["ram_chunks"]]
        path = args.out / f"{name}.rom"
        output = args.out / f"{name}.tsv"
        capture_meta = args.out / f"{name}-capture.json"
        expected_meta = dict(rom_sha256=hashlib.sha256(rom).hexdigest(),
                             fixtures_sha256=hashlib.sha256(json.dumps(fixtures, sort_keys=True).encode()).hexdigest())
        if not args.reuse:
            path.write_bytes(rom)
            run(args.openmsx.resolve(), path.resolve(), tcl_script(fixtures, output.resolve()), args.out.resolve(), name)
            capture_meta.write_text(json.dumps(expected_meta), encoding="utf-8")
        elif not capture_meta.exists() or json.loads(capture_meta.read_text()) != expected_meta:
            raise ValueError(f"Capture cache differs from current ROM/fixtures: {name}. Run without --reuse.")
        captures[name] = read_rows(output, fixtures)
        if expected_helpers is not None:
            for chunk, expected in expected_helpers:
                offset = chunk["address"] - RAM_BASE if chunk["address"] < SIDE_BASE else RAM_END - RAM_BASE + chunk["address"] - SIDE_BASE
                assert captures[name][1][offset:offset + len(expected)] == expected, f"Startup installation failed: {name}"
        hashes[name] = hashlib.sha256(rom).hexdigest()
        print(f"{name}: captured {len(captures[name][0])} function returns", flush=True)
    counts = verify(fixtures, captures)
    smoke = smoke_test(args.openmsx.resolve(), source, args.out.resolve())
    report = dict(kind="arranged Z80 function diagnostics", cases_per_rom=len(fixtures),
                  checks=counts, rom_sha256=hashes, keyboard_smoke=smoke,
                  restrictions=["not a full campaign playthrough", "not hardware verification"])
    (args.out / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
