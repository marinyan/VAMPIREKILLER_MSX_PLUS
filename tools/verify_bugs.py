"""Original-Z80 regression checks for independently selectable corrections.

These are arranged function/segment tests, not a full campaign. They run the
cartridge code in openMSX, intercept sound/rendering calls, and check stack,
bank restoration, resident-code integrity, and positive/negative controls.
"""
from pathlib import Path
import argparse
import hashlib
import json

from feature_catalog import CATALOG
from fixes.stairs import FIX as STAIRS
from fixes.trap_contact import FIX as TRAP_CONTACT
from fixes.trap_attack import FIX as TRAP_ATTACK
from fixes.patrol_timer import FIX as PATROL_TIMER
from fixes.mummy_start import FIX as MUMMY_START
from fixes.reform_hp import FIX as REFORM_HP
from fixes.stun_hp import FIX as STUN_HP
from fixes.hourglass import FIX as HOURGLASS
from fixes.actor_alloc import FIX as ACTOR_ALLOC
from fixes.projectile_alloc import FIX as PROJECTILE_ALLOC
from fixes.empty_projectile import FIX as EMPTY_PROJECTILE
from fixes.projectile_box import FIX as PROJECTILE_BOX
from fixes.crouch_fall import FIX as CROUCH_FALL
from fixes.platform_land import FIX as PLATFORM_LAND
from fixes.platform_turn import FIX as PLATFORM_TURN
from fixes.shop_input import FIX as SHOP_INPUT
from fixes.boss_spawn import FIX as BOSS_SPAWN
from fixes.weapon_owner import FIX as WEAPON_OWNER
from fixes.axe_wall import FIX as AXE_WALL
from fixes.hurt_clip import FIX as HURT_CLIP
from fixes.water_edge import FIX as WATER_EDGE
from fixes.bat_y import FIX as BAT_Y
from fixes.jumper_land import FIX as JUMPER_LAND
from fixes.water_pending import FIX as WATER_PENDING
from fixes.actor_order import FIX as ACTOR_ORDER
from fixes.phantom_gate import FIX as PHANTOM_GATE
from patches import SOURCE_SHA256, make_selected_rom
from verify_emulator import read_rows, run, tcl_script

ROOT = Path(__file__).resolve().parents[1]
NEW_FIXES = (STAIRS, TRAP_CONTACT, TRAP_ATTACK, PATROL_TIMER, MUMMY_START, REFORM_HP, STUN_HP, HOURGLASS,
             ACTOR_ALLOC, PROJECTILE_ALLOC, EMPTY_PROJECTILE, PROJECTILE_BOX, CROUCH_FALL, PLATFORM_LAND,
             PLATFORM_TURN, SHOP_INPUT, BOSS_SPAWN, WEAPON_OWNER, AXE_WALL, HURT_CLIP,
             WATER_EDGE, BAT_Y, JUMPER_LAND, WATER_PENDING, ACTOR_ORDER, PHANTOM_GATE)


def fixtures():
    cases = []

    def add(group, address, *, player=None, memory=None, registers=None, steps=None, tiles=None, **metadata):
        cases.append(dict(name=f"{group}-{len(cases)}", group=group,
                          player=bytes(player or bytes(80)).hex(), memory=memory or {},
                          registers=registers or {}, steps=steps or [(address, {}, {})], tiles=tiles or [],
                          metadata=metadata))

    for address in (0x6E30, 0x6E6A, 0x6EA2, 0x6EDD):
        for counter in range(256):
            add("stairs", address, memory={0xC42B: counter}, counter=counter)
    for state in range(8):
        for attack in (0, 1, 4):
            for trap in (0, 1, 2):
                player = bytearray(80)
                player[0], player[2], player[3], player[5], player[7] = state, attack, 7, 128, 128
                add("trap", 0x85A6, player=player, memory={0xC580: bytes([trap, 100, 128, 0, 0, 0, 0, 0]).hex()},
                    state=state, attack=attack, trap=trap)
    for timer in (0, 1, 2, 95, 96, 255):
        for direction in (0, 128):
            actor = bytearray(128)
            actor[0], actor[10], actor[12], actor[16] = 6, direction, timer, 31
            add("patrol_timer", 0xA60F, memory={0xC800: actor.hex()}, timer=timer)
    for velocity in (0, 1, 0x160, 0xFEA0, 0x8000, 0xFFFF):
        actor = bytearray([0xA5]) * 128
        actor[9:11] = velocity.to_bytes(2, "little")
        add("mummy_start", 0xB87C, memory={0xC800: actor.hex()}, velocity=velocity)
    for kind, group in ((9, "reform_hp"), (0x18, "stun_hp")):
        for health in (0, 1, 2, 127, 128, 255):
            for no_survival in (0, 1):
                actor = bytearray(128)
                actor[0], actor[13] = kind, health
                add(group, 0x9A6B, memory={0xC800: actor.hex(), 0xCFFF: no_survival if kind == 9 else 0,
                                         0xCE0B: no_survival if kind == 0x18 else 0},
                    health=health, no_survival=no_survival)
    for flags in (0, 1, 2, 3, 128, 129, 255):
        for remaining in (0, 1, 2, 127, 255):
            player = bytearray(80)
            player[27] = remaining
            add("hourglass", 0x63B7, player=player, memory={0xD010: flags}, flags=flags)
    for inventory in (1, 0x11, 0x21, 0x31, 0xA1):
        for remaining in (0, 1, 7, 16, 255):
            for flags in (0, 1, 3):
                player = bytearray(80)
                player[33] = remaining
                for boss in (False, True):
                    steps = ([(0x70DC, {}, {})] if boss else []) + [(0x62EC, {}, {})]
                    add("shield_transition", 0x62EC, player=player,
                        memory={0xD010: flags, 0xC701: inventory}, steps=steps,
                        inventory=inventory, remaining=remaining, flags=flags, boss=boss)
    for group in ("actor_alloc", "projectile_alloc", "boss_spawn"):
        for free in range(15 if group != "projectile_alloc" else 9):
            for occupied in (0, 6, 7) if group != "projectile_alloc" else (0, 7, 8):
                for restricted in ((0, 1) if group == "projectile_alloc" else (0,)):
                    actors = bytearray(896 if group != "projectile_alloc" else 1024)
                    for index in range(occupied):
                        actors[index * 128] = 1
                    sat = bytearray(72)
                    free_indices = list(range(free)) if group != "projectile_alloc" else list(range(17, 17 - free, -1))
                    for index in range(18):
                        sat[index * 4] = 224 if index in free_indices else 0x40 + index
                    if group == "projectile_alloc":
                        memory = {0xD700: actors.hex(), 0xD638: sat.hex(), 0xCFF9: 255, 0xCE03: restricted}
                        address, regs = 0x9F83, {}
                        needed = 2
                        available = min(free, 2 if restricted else 8)
                        found = occupied < 8
                    else:
                        memory = {0xC800: actors.hex(), 0xD638: sat.hex(), 0xCE01: 2}
                        address, regs = (0xBCF9, {}) if group == "boss_spawn" else (0x5F1D, {"BC": 0x13, "DE": 0x9090})
                        needed, available, found = 8, free, occupied < 7
                    add(group, address, memory=memory, registers=regs, needed=needed, available=available,
                        found=found, free_indices=free_indices, initial_sat=sat.hex())
    for slot in (0, 1):
        for phase in (0, 1, 2, 3):
            for kind in range(7):
                for dx in (0, 13, 14, 15, 19, 20, 25):
                    player = bytearray(80)
                    for index in (0, 1):
                        player[48 + index * 16 + 4] = 128
                        player[48 + index * 16 + 5] = 250
                    player[48 + slot * 16:50 + slot * 16] = bytes([phase, kind])
                    player[53 + slot * 16] = 128 + dx
                    add("projectile_rect", 0x84F0, player=player, registers={"DE": 0x8080, "HL": 0x1008},
                        slots=[list(player[48:64]), list(player[64:80])])
    for selector in (0, 1, 2):
        for state in (0, 1, 3, 4, 5):
            for y in (94, 96, 100, 104, 110):
                for active in (0, 1):
                    player = bytearray(80)
                    player[0], player[5], player[7], player[25] = state, y, 128, selector
                    platform = bytes([active, 96, 100, 0, 20, 0, 3, active, 88, 120, 128, 30, 0, 3])
                    for address in (0x6D3B, 0x6FF2):
                        add("platform_land", address, player=player, memory={0xC598: platform.hex()},
                            selector=selector, state=state, y=y, active=active, entry=address)
    for selector in (1, 2):
        for direction in (0, 128):
            for counter in (0, 18, 19, 20, 254, 255):
                player = bytearray(80)
                player[5], player[7], player[25] = 96, 128, selector
                platform = bytes([1, 96, 100, direction, 20, 0, counter]) * 2
                add("platform_turn", 0x6BAF, player=player, memory={0xC598: platform.hex()},
                    registers={"AF": selector << 8}, counter=counter, direction=direction)
    for solid in (0, 1):
        for support in (0, 1):
            for attack in (0, 1):
                player = bytearray(80)
                player[0], player[2], player[5], player[7], player[25] = 2, attack, 128, 128, support
                add("crouch_fall", 0x6DA9, player=player, memory={0xC007: 2}, solid=solid,
                    support=support, attack=attack, tiles=[(x, 128, 1) for x in range(112, 145, 8)] if solid else [])
    for previous in range(4):
        for held in range(4):
            for pressed in range(4):
                sequence = [held, pressed, 0, pressed]
                add("shop_input", 0x9387, memory={0xC709: previous}, previous=previous, sequence=sequence,
                    steps=[(0x9387 if index == 0 else 0x951F, {0xC40C: mask}, {}) for index, mask in enumerate(sequence)])
    for kind in (1, 2, 3, 4):
        for first in ((0, 0), (1, 0), (2, 2), (2, 3)):
            for second in ((0, 0), (1, 0), (2, 4), (1, 5)):
                player = bytearray(80)
                player[48], player[49] = first
                player[64], player[65] = second
                player[63], player[79] = 0x55, 0xAA
                add("weapon_owner_pickup", 0x8D76, player=player, registers={"AF": kind << 8}, kind=kind)
    for slot in (0, 1):
        for old_owner in (0, 1, 255):
            for weapon in (1, 2, 3, 4):
                player = bytearray(80)
                base = 48 + slot * 16
                player[base], player[base + 1], player[base + 4], player[base + 5], player[base + 15] = 2, 3, 128, 0, old_owner
                for group, entry in (("weapon_owner_lose", 0x8E93), ("weapon_owner_exit", 0x74CE), ("weapon_owner_wall", 0x74A5)):
                    add(group, entry, player=player, memory={0xC416: weapon},
                        registers={"IX": 0xC450 + slot * 16, "HL": 0xC433}, slot=slot, old_owner=old_owner, weapon=weapon)
    for full in (False, True):
        for poisoned in (0, 255):
            player = bytearray(80)
            player[49] = 2 if full else 0
            player[65] = 3 if full else 0
            for base in (48, 64):
                player[base + 13:base + 16] = bytes([poisoned]) * 3
            add("projectile_claim", 0x71BE, player=player, memory={0xC436: 2}, full=full)
            add("holy_claim", 0x71AA, player=player, memory={0xC417: 0x10}, full=full)
    for actual_slot in (0, 1):
        for kind in (2, 3, 4, 5):
            for notification in (1, 2, 3):
                for inspect_actual in ((False, True) if kind == 3 else (False,)):
                    player = bytearray(80)
                    for slot in (0, 1):
                        base = 48 + slot * 16
                        player[base:base + 9] = bytes([2, kind if slot == actual_slot else 3, 0, 1, 128, 128 if slot == actual_slot else 220, 0, 0, 0])
                    inspected = actual_slot if inspect_actual else 1 - actual_slot
                    obj = bytes([1, 112 if notification == 1 else 96, 120 if notification == 1 else 112, 0, notification] + [0] * 11)
                    add("axe_wall", 0x80A6, player=player, memory={0xC470: obj.hex(), 0xC416: 3},
                        steps=[(0x80A6, {}, {}), (0x748C, {}, {"IX": 0xC450 + inspected * 16})],
                        inspected=inspected, actual=actual_slot, kind=kind, notification=notification)
    for state in (0, 1, 4, 5):
        for left in (False, True):
            for fraction in (0, 128, 255):
                for solid in (False, True):
                    for x in ((88, 0, 9) if left else (71, 253, 247)):
                        player = bytearray(80)
                        player[0], player[5], player[7], player[6] = state, 128, x, fraction
                        delta = -640 if left else 640
                        next_x = ((x * 256 + fraction + delta) & 65535) >> 8
                        wall_x = ((next_x - 8 if left else next_x + 8) & 255) & 248
                        add("hurt_horizontal", 0x6C94, player=player, registers={"BC": delta & 65535},
                            tiles=[(wall_x, 120, 1)] if solid else [], state=state, x=x, fraction=fraction,
                            delta=delta, solid=solid, left=left)
    for x in (0, 6, 7, 92, 248, 249, 255):
        for initial_y in (132, 136):
            for counter in range(21):
                for sample in (None, -7, 0, 7):
                    player = bytearray(80)
                    player[0], player[5], player[7], player[10] = 5, initial_y, x, counter
                    ceiling_x = ((x + sample) & 255) & 248 if sample is not None else None
                    add("hurt_vertical", 0x6FE0, player=player, registers={"HL": 0xC42A, "BC": 0x707D, "DE": 0x1500},
                        tiles=[(ceiling_x, 96, 1)] if sample is not None else [],
                        x=x, y=initial_y, counter=counter, ceiling_x=ceiling_x)
    for slot in (0, 1):
        for kind in (3, 4, 5):
            for weapon in range(5):
                for previous_owner in (0, 1):
                    for x in (0, 4, 128, 252, 255):
                        for y in (128, 220):
                            player = bytearray(80)
                            base = 48 + slot * 16
                            player[base:base + 6] = bytes([2, kind, 0, 1, y, x])
                            player[base + 15] = previous_owner
                            add("water_edge", 0x74CE, player=player, memory={0xC416: weapon},
                                registers={"IX": 0xC450 + slot * 16}, kind=kind, weapon=weapon,
                                previous_owner=previous_owner, x=x, y=y, slot=slot)
    for player_y in (64, 96, 160, 192):
        for bat_y in (48, 80, 96, 144):
            for x in (32, 64, 128, 192):
                for direction in (0, 128):
                    actor = bytearray(128)
                    actor[0], actor[1], actor[3], actor[5], actor[10], actor[19], actor[21] = 0x1F, 1, bat_y, x, direction, 0xAA, 0x55
                    add("bat_y", 0xB13E, memory={0xC800: actor.hex(), 0xC425: player_y},
                        player_y=player_y, bat_y=bat_y, x=x)
    for y in (56, 60, 80, 188, 192):
        for supported in (False, True):
            for velocity in (0, 0x100, 0x700, 0x7F0):
                actor = bytearray(128)
                actor[0], actor[1], actor[3], actor[5], actor[6], actor[12] = 0x23, 1, y, 128, 1, 17
                actor[7:9] = velocity.to_bytes(2, "little")
                add("jumper_land", 0xB268, memory={0xC800: actor.hex()}, y=y, supported=supported,
                    tiles=[(tile_x, y & 248, 1 if supported else 0) for tile_x in (112, 120, 128, 136)])
    for first in ((0, 0), (1, 0), (1, 2), (2, 2)):
        for second in ((0, 0), (1, 0), (2, 5)):
            for attack in range(5):
                for weapon in range(5):
                    for direction, address in ((1, 0x7194), (0, 0x71A1)):
                        player = bytearray(80)
                        player[0], player[2], player[22] = 1, attack, weapon
                        player[48:50], player[64:66] = bytes(first), bytes(second)
                        for base in (48, 64):
                            player[base + 13:base + 16] = bytes([255]) * 3
                        add("water_pending", address, player=player, memory={0xC417: 0x30},
                            first=first, second=second, attack=attack, weapon=weapon, direction=direction)
    for direction in (4, 8):
        for water_tick, second_sword, inventory in ((6, True, 8), (7, True, 8), (8, True, 8),
                                                     (None, True, 8), (6, False, 8), (6, True, 0)):
            player = bytearray(80)
            player[5], player[7] = 192, 80
            steps, inputs = [], []
            for tick in range(12):
                mask = 32 if tick == 0 else 16 if tick == 1 or tick == 5 and second_sword else 0
                if tick == water_tick:
                    mask = direction
                inputs.append(mask)
                steps.extend([(0x6B39, {0xC006: mask, 0xC007: mask, 0xC003: tick}, {}),
                              (0x710D, {}, {}), (0x6B27, {}, {})])
            add("water_pending_sequence", 0x6B39, player=player,
                memory={0xC416: 2, 0xC417: 0x30, 0xC701: inventory}, steps=steps,
                direction=direction, water_tick=water_tick, second_sword=second_sword,
                inventory=inventory, inputs=inputs)
    for owner in range(7):
        for empty in (None, *[slot for slot in range(7) if slot != owner]):
            for expire in (False, True):
                for free_parts in (0, 14):
                    actors = bytearray(896)
                    for slot in range(7):
                        base = slot * 128
                        actors[base], actors[base + 3], actors[base + 5], actors[base + 12] = 0x1E, 80, 128, 31 + slot
                    if empty is not None:
                        actors[empty * 128] = 0
                    actors[owner * 128 + 12], actors[owner * 128 + 31] = (1 if expire else 2), 1
                    sat = bytearray(72)
                    for index in range(18):
                        sat[index * 4] = 224 if index < free_parts else 64
                    add("actor_order", 0x98EC, memory={0xC800: actors.hex(), 0xD638: sat.hex()},
                        initial=actors.hex(), owner=owner, empty=empty, expire=expire, free_parts=free_parts)
    for owner in (0, 2, 5):
        for clock in (0, 1):
            actors = bytearray(896)
            for slot in range(owner):
                base = slot * 128
                actors[base], actors[base + 3], actors[base + 5], actors[base + 12] = 0x1E, 80, 128, 31
            base = owner * 128
            actors[base], actors[base + 3], actors[base + 5], actors[base + 6], actors[base + 126] = 2, 192, 128, 1, 1
            add("actor_order_water", 0x98EC, memory={0xC800: actors.hex(), 0xD010: clock},
                initial=actors.hex(), owner=owner, clock=clock,
                tiles=[(x, 192, 0) for x in (112, 120, 128, 136, 144)])
    for expire in (False, True):
        for timer in (31, 32):
            actors = bytearray(896)
            actors[128], actors[129], actors[131], actors[133], actors[137], actors[138] = 0x10, 3, 176, 135, 192, 254
            actors[141], actors[142], actors[143], actors[144], actors[145] = 8, 7, 0x52, 1, timer
            actors[256], actors[259], actors[261], actors[268], actors[287] = 0x1E, 80, 128, 1 if expire else 2, 1
            player = bytearray(80)
            player[0], player[5], player[7] = 5, 77, 164
            add("actor_order_armor", 0x98EC, player=player, memory={0xC800: actors.hex()},
                initial=actors.hex(), owner=2, expire=expire, timer=timer)
    for gate in (0, 1, 2, 3):
        for facing in (0, 1):
            for x in (0, 6, 8, 14, 16, 20, 226, 228, 244, 252):
                for y in (0, 2, 38, 49, 50, 52, 96):
                    player = bytearray(80)
                    player[5], player[7], player[12] = y, x, facing
                    delta = -512 if facing else 512
                    add("phantom_gate", 0x6C73, player=player, memory={0xC5AC: gate, 0xC5AD: 96 if gate else 0, 0xC5AE: 240 if gate else 0},
                        registers={"BC": delta & 65535}, gate=gate, facing=facing, x=x, y=y, delta=delta)
    return cases


def script_for(cases, output, rom, info):
    script = tcl_script(cases, output).replace("0xf200", "0xf0a0")
    script = script.replace("debug write memory 0xf0d0 0", "debug write memory 0xf0d0 160").replace("0xf0d1 0xf2", "0xf0d1 0xf0")
    script = script.replace('[binary encode hex [debug read_block memory 0xd460 64]]"',
                            '[binary encode hex [debug read_block memory 0xd460 64]]\t'
                            '[binary encode hex [debug read_block memory 0xc700 32]]\t'
                            '[binary encode hex [debug read_block memory 0xcf00 256]]\t'
                            '[binary encode hex [debug read_block memory 0xd000 32]]\t'
                            '[reg BC]\t[reg DE]\t[reg HL]\t[reg IX]\t[reg IY]\t[peek 0xf0f2]\t'
                            '[binary encode hex [debug read_block memory 0xc598 14]]\t[peek 0xce01]"')
    stops = "\n".join(f'debug set_bp {address} {{$::active && [lindex [lindex $::fixtures $::ci] 5] eq "stairs"}} return_now'
                      for address in (0x6E36, 0x6E70, 0x6EA8, 0x6EE3))
    script = script.replace("debug set_bp 0xf0a0 {} returned", "debug set_bp 0xf0a0 {} returned\n" + stops)
    script = script.replace("debug set_bp 0xf0a0 {} returned", '''debug set_bp 0xf0a0 {} returned
 debug set_bp 0x938a {$::active && [lindex [lindex $::fixtures $::ci] 5] eq "shop_input"} return_now
 debug set_bp 0x93ff {$::active && [lindex [lindex $::fixtures $::ci] 5] eq "shop_input"} return_now
 debug set_bp 0x62ef {$::active && [lindex [lindex $::fixtures $::ci] 5] eq "shield_transition"} return_now
 debug set_bp 0x490a {$::active && [lindex [lindex $::fixtures $::ci] 5] eq "boss_spawn"} return_now''')
    script = script.replace("debug set_bp 0xf0a0 {} returned", '''debug set_bp 0xf0a0 {} returned
 debug set_bp 0x6fe3 {$::active && [lindex [lindex $::fixtures $::ci] 5] eq "hurt_vertical"} return_now
 debug set_bp 0x7496 {$::active && [lindex [lindex $::fixtures $::ci] 5] eq "axe_wall"} return_now
 debug set_bp 0x8e9a {$::active && ([string match "weapon_owner*" [lindex [lindex $::fixtures $::ci] 5]] || [lindex [lindex $::fixtures $::ci] 5] eq "axe_wall")} return_now
 debug set_bp 0x8992 {$::active && ([lindex [lindex $::fixtures $::ci] 5] eq "weapon_owner_wall" || [lindex [lindex $::fixtures $::ci] 5] eq "axe_wall")} return_now''')
    script = script.replace(" putmem $memory\n putregs $regs", ''' putmem $memory
 if {[lindex $cfg 5] eq "shop_input"} {
  keymatrixup 6 1
  keymatrixup 8 1
  set keys [peek 0xc40c]
  if {$keys & 2} {keymatrixdown 6 1}
  if {$keys & 1} {keymatrixdown 8 1}
 }
 putregs $regs''')
    script = script.replace("debug set_bp 0x509f {$::active} return_now", "debug set_bp 0x509f {$::active} record_sound")
    script = script.replace("debug set_bp 0xf0a0 {} returned", '''debug set_bp 0xf0a0 {} returned
 debug set_bp 0x993b {$::active && [string match "actor_order*" [lindex [lindex $::fixtures $::ci] 5]]} {puts $::output "EVENT\\t$::ci\\t$::si\\tactor_dispatch\\t[expr {([reg IX]-0xc800)/128}]"}
 debug set_bp 0x99b9 {$::active && [string match "actor_order*" [lindex [lindex $::fixtures $::ci] 5]]} {puts $::output "EVENT\\t$::ci\\t$::si\\tactor_move\\t[expr {([reg IX]-0xc800)/128}]"}''')
    script = script.replace("debug set_bp 0xf0a0 {} returned", '''debug set_bp 0xf0a0 {} returned
 debug set_bp 0x4566 {$::active && [string match "water_pending*" [lindex [lindex $::fixtures $::ci] 5]]} return_now
 debug set_bp 0x5593 {$::active && [lindex [lindex $::fixtures $::ci] 5] eq "water_pending_sequence"} return_now''')
    script = script.replace("proc begin {}", '''proc record_sound {} {
 global output ci si
 puts $output "EVENT\\t$ci\\t$si\\tsound\\t[expr {[reg AF] >> 8}]"
 return_now
}
proc begin {}''')
    guards = []
    for chunk in info.get("ram_chunks", []):
        expected = rom[chunk["source_offset"]:chunk["source_offset"] + chunk["size"]].hex()
        guards.append(f'if {{[binary encode hex [debug read_block memory {chunk["address"]} {chunk["size"]}]] ne "{expected}"}} {{error "resident code changed"}}')
    script = script.replace("if {[reg SP] != 0xf0d2}", "\n".join(guards) + "\n if {[reg SP] != 0xf0d2}")
    return script


def extras(path):
    states, sounds = {}, {}
    for line in path.read_text().splitlines():
        fields = line.split("\t")
        if fields[0].isdigit():
            states[int(fields[0]), int(fields[1])] = ([bytes.fromhex(value) for value in fields[12:15]] +
                                                    [int(value) for value in fields[15:21]] + [bytes.fromhex(fields[21]), int(fields[22])])
        elif fields[0] == "EVENT" and fields[3] == "sound":
            sounds.setdefault((int(fields[1]), int(fields[2])), []).append(int(fields[4]))
        elif fields[0] == "EVENT" and fields[3] in ("actor_dispatch", "actor_move"):
            sounds.setdefault((int(fields[1]), int(fields[2]), fields[3]), []).append(int(fields[4]))
    return states, sounds


def verify(cases, baseline, current, enabled):
    rows, extra, sounds = current
    base_rows, base_extra, base_sounds = baseline
    counts, reproduced = {}, set()
    for ci, case in enumerate(cases):
        key, group, m = (ci, 0), case["group"], case["metadata"]
        row, old = rows[key], base_rows[key]
        p, original_player = row[0], old[0]
        actor, original_actor = row[2][:128], old[2][:128]
        expected_player, expected_actor = bytearray(original_player), bytearray(original_actor)
        if group == "stairs":
            expected = (m["counter"] + 1) & 255
            if "stairs" in enabled and expected == 0:
                expected = 8
            expected_player[11] = expected
            assert p == expected_player, (group, m, p[11], expected)
            assert extra[key][3] >> 8 == expected, (group, "B", extra[key][3], expected)
            if m["counter"] == 255:
                assert original_player[11] == 0
                reproduced.add("stairs")
        elif group == "trap":
            prevented = "trap_contact" in enabled and m["state"] == 5
            hit = m["trap"] != 0 and m["state"] != 6 and not prevented
            if prevented:
                expected_player = bytearray.fromhex(case["player"])
                assert row[1][5] == 32
            else:
                assert row[1] == old[1]
            if hit and "trap_attack" in enabled:
                expected_player[2:4] = bytes(2)
            assert p == expected_player, (group, m, p.hex(), expected_player.hex())
            if m["trap"] and m["state"] == 5:
                assert old[1][5] < 32
                reproduced.add("trap_contact")
            if m["trap"] and m["state"] == 0 and m["attack"]:
                assert original_player[2] == m["attack"]
                reproduced.add("trap_attack")
        elif group == "patrol_timer":
            if "patrol_timer" in enabled and m["timer"] == 0:
                expected_actor[12] = 96
            assert actor == expected_actor, (group, m, actor.hex(), expected_actor.hex())
            if m["timer"] == 0:
                assert original_actor[12] == 0
                reproduced.add(group)
        elif group == "mummy_start":
            if group in enabled:
                expected_actor[9:11] = bytes(2)
            assert actor == expected_actor, (group, m, actor.hex(), expected_actor.hex())
            if m["velocity"]:
                assert int.from_bytes(original_actor[9:11], "little") == m["velocity"]
                reproduced.add(group)
        elif group in ("reform_hp", "stun_hp"):
            if group in enabled and not m["no_survival"]:
                expected_actor[13] = 2 if group == "reform_hp" else 1
            assert actor == expected_actor, (group, m, actor.hex(), expected_actor.hex())
            if not m["no_survival"] and m["health"] == 0:
                assert original_actor[13] == 0
                reproduced.add(group)
        elif group == "hourglass":
            expected = m["flags"] & ~1 if group in enabled else m["flags"]
            assert extra[key][2][16] == expected, (group, m, extra[key][2][16], expected)
            assert p == original_player == bytes(80)
            assert sounds.get(key, []) == ([252] if group in enabled and m["flags"] & 1 else [])
            if m["flags"] & 1:
                assert base_extra[key][2][16] & 1
                reproduced.add(group)
        elif group == "shield_transition":
            final = len(case["steps"]) - 1
            expected_remaining = m["remaining"] if "shield_fix" in enabled and not m["boss"] else 0
            inventory = m["inventory"] & 0x80 if m["boss"] else m["inventory"]
            if "shield_fix" in enabled and not expected_remaining:
                inventory &= 0xCF
            expected_flags = m["flags"] & ~1 if "hourglass" in enabled else m["flags"]
            assert rows[ci, final][0][33] == expected_remaining
            assert extra[ci, final][0][1] == inventory
            assert extra[ci, final][2][16] == expected_flags
        elif group in ("actor_alloc", "projectile_alloc"):
            expected_sprites = bytearray(old[3])
            if group in enabled and m["found"] and m["available"] < m["needed"]:
                for index in m["free_indices"][:m["available"]]:
                    expected_sprites[index * 4] = 224
            assert row[3] == expected_sprites, (group, m, row[3].hex(), expected_sprites.hex())
            assert row[2] == old[2] and row[7] == old[7], (group, "record side effects")
            assert extra[key][1] == base_extra[key][1], (group, "allocation signals")
            if m["found"] and 0 < m["available"] < m["needed"]:
                assert old[3] != bytes.fromhex(m["initial_sat"])
                reproduced.add(group)
        elif group == "boss_spawn":
            success = m["found"] and m["available"] >= 8
            expected_phase = 3 if success or group not in enabled else 2
            assert row[0] == old[0]
            # CE01 is not in the generic player capture; inspect it through the configured extra block below.
            assert extra[key][10] == expected_phase, (group, m, extra[key][10], expected_phase)
            if not success and group in enabled:
                assert row[3] == bytes.fromhex(m["initial_sat"]), (group, "preflight must avoid partial reservations")
            if not success:
                assert base_extra[key][10] == 3
                reproduced.add(group)
        elif group == "projectile_rect":
            height, radius, expected_slot = 16, 8, 1
            hit = False
            for index, slot in enumerate(m["slots"]):
                if "projectile_box" in enabled:
                    height, radius = 16, 8
                radius = (radius + 6) & 255
                if "empty_projectile" in enabled and (not slot[0] or not 2 <= slot[1] <= 5):
                    continue
                if "screen_edges" in enabled and slot[1] == 2 and slot[13]:
                    continue
                if abs(slot[5] - 128) >= radius:
                    continue
                previous_height = height
                height = (height + (6 if slot[1] == 2 else 12)) & 255
                if (slot[4] - 128 + previous_height) & 255 < height:
                    expected_slot, hit = index, True
                    break
            assert bool(row[6] & 1) == hit, (group, m, enabled, row[6], hit)
            assert extra[key][7] == 0xC450 + expected_slot * 16, (group, "hit slot")
            assert extra[key][5] == height * 256 + radius, (group, "dimensions", extra[key][5], height, radius)
            old_slot = (base_extra[key][7] - 0xC450) // 16
            if old[6] & 1 and (not m["slots"][old_slot][0] or not 2 <= m["slots"][old_slot][1] <= 5):
                reproduced.add("empty_projectile")
            if old[6] & 1 and old_slot == 1 and 2 <= m["slots"][1][1] <= 5 and abs(m["slots"][1][5] - 128) >= 14:
                reproduced.add("projectile_box")
            # The baseline supplies concrete original false-positive examples, checked against the same independent model.
        elif group == "platform_land":
            expected_y = m["y"] & 248
            if group in enabled and m["active"] and m["selector"] and m["state"] in (1, 5):
                expected_y = (96 if m["selector"] == 1 else 88) & 248
            assert p[5] == expected_y, (group, m, p[5], expected_y)
            assert extra[key][9] == base_extra[key][9], (group, "platform changed")
            if m["selector"] and m["active"] and m["state"] in (1, 5) and m["y"] >= 104:
                reproduced.add(group)
        elif group == "platform_turn":
            stationary = (m["counter"] + 1) & 255 == 20
            expected_x = 128 if group in enabled and stationary else original_player[7]
            assert p[7] == expected_x, (group, m, p[7], expected_x)
            assert extra[key][9] == base_extra[key][9]
            if stationary:
                assert original_player[7] != 128
                reproduced.add(group)
        elif group == "crouch_fall":
            should_fall = not m["solid"] and not m["support"]
            expected_state = 4 if group in enabled and should_fall else original_player[0]
            assert p[0] == expected_state, (group, m, p[0], expected_state)
            if should_fall:
                assert original_player[0] == 2
                reproduced.add(group)
        elif group == "shop_input":
            held = m["previous"]
            for si, mask in enumerate(m["sequence"]):
                actual = extra[ci, si][0][9]
                if si == 0:
                    held = mask if group in enabled else held
                else:
                    assert rows[ci, si][6] >> 8 == mask & ~held, (group, m, si, rows[ci, si][6] >> 8, mask & ~held)
                    held = mask
                assert actual == held, (group, m, si, actual, held)
            if m["previous"] == 2 and m["sequence"][:2] == [0, 2]:
                assert base_rows[ci, 1][6] >> 8 == 0
                reproduced.add(group)
        elif group == "weapon_owner_pickup":
            if "weapon_owner" in enabled:
                before = bytes.fromhex(case["player"])
                for offset in (48, 64):
                    expected_player[offset + 15] = before[offset] | before[offset + 1]
            assert p == expected_player, (group, m, p.hex(), expected_player.hex())
        elif group in ("weapon_owner_lose", "weapon_owner_exit", "weapon_owner_wall"):
            lost = not ("weapon_owner" in enabled and m["old_owner"])
            # The ordinary exit only loses axe/cross equipment, as in the original.
            if group == "weapon_owner_exit" and m["weapon"] not in (3, 4):
                lost = False
            assert row[1][6] == (0 if lost else m["weapon"]), (group, m, row[1][6])
            if group != "weapon_owner_lose":
                cleared = bytes(4) + bytes([224]) + bytes(11)
                assert p[48 + m["slot"] * 16:64 + m["slot"] * 16] == cleared, (group, "projectile not cleared")
            if m["old_owner"] and (group != "weapon_owner_exit" or m["weapon"] in (3, 4)):
                assert old[1][6] == 0
                reproduced.add("weapon_owner")
        elif group in ("projectile_claim", "holy_claim"):
            chosen = 64 if group == "holy_claim" else 48
            if group == "holy_claim" or not m["full"]:
                offsets = ([13] if "screen_edges" in enabled else []) + ([14] if "axe_wall" in enabled else []) + ([15] if "weapon_owner" in enabled else [])
                for offset in offsets:
                    expected_player[chosen + offset] = 0
            assert p == expected_player, (group, m, p.hex(), expected_player.hex())
        elif group == "water_pending":
            protected = (m["second"] == (1, 0) and m["attack"] != 0 and m["weapon"] >= 2
                         and m["first"][0] != 1)
            if "water_pending" in enabled and protected:
                expected_player = bytearray.fromhex(case["player"])
                assert row[1][7] == 0x30, (group, m, "spent hearts on a rejected claim")
            else:
                assert row[1] == old[1], (group, m, "changed normal claim cost")
                if not m["second"][1]:
                    if "water_pending" in enabled and "fall_attack" in enabled:
                        expected_player[64:80] = bytes(16)
                        expected_player[65], expected_player[72] = 5, m["direction"]
                    for offset, fix_id in ((13, "screen_edges"), (14, "axe_wall"), (15, "weapon_owner")):
                        if fix_id in enabled:
                            expected_player[64 + offset] = 0
            assert p == expected_player, (group, m, p.hex(), expected_player.hex())
            if protected:
                assert original_player[65] == 5 and old[1][7] == 0x25
                reproduced.add("water_pending")
        elif group == "water_pending_sequence":
            blocked = (m["second_sword"] and m["inventory"] == 8 and m["water_tick"] in (6, 7, 8))
            for tick in range(12):
                state = rows[ci, tick * 3 + 2]
                source_state = base_rows[ci, tick * 3 + 2]
                if tick < (m["water_tick"] or 12) or not blocked or "water_pending" not in enabled:
                    assert state[0][:64] == source_state[0][:64], (group, m, tick, "first throw changed")
                    assert state[0][64:77] == source_state[0][64:77], (group, m, tick, "normal water changed")
                    assert state[1] == source_state[1], (group, m, tick, "normal heart cost changed")
                else:
                    assert state[1][7] == 0x30, (group, m, tick, "rejected water spent hearts")
                    assert state[0][65] == (0 if tick < 8 else 2), (group, m, tick, "pending sword lost")
            final, source_final = rows[ci, 35], base_rows[ci, 35]
            if blocked:
                assert source_final[1][7] == 0x25
                assert source_final[0][65] == (2 if m["water_tick"] == 8 else 5)
            if blocked and "water_pending" in enabled:
                assert final[0][49] == final[0][65] == 2
            if not m["second_sword"] and m["inventory"] == 8:
                assert final[0][65] == 5 and final[1][7] == 0x25
        elif group.startswith("actor_order"):
            initial = bytes.fromhex(m["initial"])
            dispatch = sounds.get((*key, "actor_dispatch"), [])
            old_dispatch = base_sounds.get((*key, "actor_dispatch"), [])
            live = [slot for slot in range(7) if initial[slot * 128]]
            expected = [slot for slot in live if group != "actor_order_water" or not m["clock"] or slot != m["owner"]]
            if "actor_order" in enabled:
                assert dispatch == expected, (group, m, dispatch, expected)
                assert extra[key][6] == 0xCB80, (group, "owner cursor", extra[key][6])
                for slot in live:
                    if slot != m["owner"]:
                        timer_offset = 17 if initial[slot * 128] == 0x10 else 12
                        assert row[2][slot * 128 + timer_offset] == initial[slot * 128 + timer_offset] - 1, (group, slot, "timer updated twice")
                if group == "actor_order":
                    births = [slot for slot in range(7) if row[2][slot * 128] == 0x24]
                    for slot in births:
                        record = row[2][slot * 128:(slot + 1) * 128]
                        assert record[12] == 1, (group, "newborn AI ran immediately")
                        assert record[2:6] == bytes.fromhex("80500082"), (group, "lost newborn's immediate movement", record[2:6].hex())
            else:
                assert row[2] == old[2], (group, "disabled behavior changed")
                assert dispatch == old_dispatch
            if len(old_dispatch) != len(set(old_dispatch)):
                reproduced.add("actor_order")
            if group == "actor_order_water":
                assert row[2] == old[2], (group, "natural water/splash behavior changed")
        elif group == "phantom_gate":
            expected_x = (m["x"] * 256 + m["delta"]) & 65535 if "phantom_gate" in enabled and m["gate"] == 0 else int.from_bytes(original_player[6:8], "little")
            assert int.from_bytes(p[6:8], "little") == expected_x, (group, m, p[6:8].hex(), expected_x)
            if m["gate"]:
                assert p == original_player, (group, "real gate changed")
            if m["gate"] == 0 and m["facing"] == 1 and m["x"] == 14 and m["y"] == 38:
                assert original_player[7] == 14
                reproduced.add("phantom_gate")
        elif group == "axe_wall":
            final, original_final = rows[ci, 1], base_rows[ci, 1]
            should_break = m["notification"] in (2, 3) and ("axe_wall" not in enabled or m["kind"] == 3 and m["inspected"] == m["actual"])
            record = final[0][48 + m["inspected"] * 16:64 + m["inspected"] * 16]
            cleared = bytes(4) + bytes([224]) + bytes(11)
            assert (record == cleared) == should_break, (group, m, enabled, record.hex(), should_break)
            # The terrain record must never receive the per-projectile marker.
            assert extra[key][1] == base_extra[key][1]
            if m["notification"] in (2, 3) and (m["kind"] != 3 or m["inspected"] != m["actual"]):
                assert original_final[0][48 + m["inspected"] * 16:64 + m["inspected"] * 16] == cleared
                reproduced.add("axe_wall")
        elif group == "hurt_horizontal":
            original_x = m["x"] * 256 + m["fraction"]
            result_x = (original_x + m["delta"]) & 65535
            if "hurt_clip" in enabled and m["state"] == 5 and m["solid"]:
                inside = (original_x + m["delta"] >= 0 and result_x >> 8 >= 8) if m["left"] else (original_x + m["delta"] < 65536 and result_x >> 8 < 248)
                if inside:
                    result_x = original_x
            assert int.from_bytes(p[6:8], "little") == result_x, (group, m, p[6:8].hex(), result_x)
            if m["state"] == 5 and m["solid"] and m["x"] in (71, 88):
                assert original_player[6:8] != bytes.fromhex(case["player"])[6:8]
                reproduced.add("hurt_clip")
        elif group == "hurt_vertical":
            source = verify.source
            index = min(m["counter"] + 1, 21) - 1
            delta = source[0x307D + index]
            delta = delta - 256 if delta >= 128 else delta
            y = m["y"]
            if "hurt_clip" in enabled and delta < 0:
                for _ in range(-delta):
                    xs = [m["x"]] + ([m["x"] - 7] if m["x"] >= 7 else []) + ([m["x"] + 7] if m["x"] < 249 else [])
                    if m["ceiling_x"] is not None and ((y - 27) & 255) & 248 == 96 and any(sample & 248 == m["ceiling_x"] for sample in xs):
                        break
                    y = (y - 1) & 255
            else:
                y = (y + delta) & 255
            assert p[5] == y, (group, m, delta, p[5], y)
        elif group == "water_edge":
            side = m["y"] < 216 and m["x"] != 128
            lost = side and m["weapon"] in (3, 4)
            if "water_edge" in enabled and m["kind"] == 5:
                lost = False
            if "weapon_owner" in enabled and m["previous_owner"]:
                lost = False
            assert row[1][6] == (0 if lost else m["weapon"]), (group, m, enabled, row[1][6], lost)
            assert p == original_player, (group, "water lifetime or clear changed")
            if side and m["kind"] == 5 and m["weapon"] in (3, 4) and not m["previous_owner"]:
                assert old[1][6] == 0
                reproduced.add(group)
        elif group == "bat_y":
            coordinate = m["bat_y"] if group in enabled else m["x"]
            transition = (m["player_y"] - coordinate - 4) & 255 < 16
            expected_actor[1] = 2 if transition else 1
            expected_actor[19] = m["bat_y"] if transition else 0xAA
            expected_actor[21] = 0 if transition else 0x55
            assert actor == expected_actor, (group, m, actor.hex(), expected_actor.hex())
            if ((m["player_y"] - m["x"] - 4) & 255 < 16) != ((m["player_y"] - m["bat_y"] - 4) & 255 < 16):
                reproduced.add(group)
        elif group == "jumper_land":
            if group in enabled and not m["supported"]:
                expected_actor[1], expected_actor[3], expected_actor[6], expected_actor[12] = 1, m["y"], 1, 17
            assert actor == expected_actor, (group, m, actor.hex(), expected_actor.hex())
            if not m["supported"]:
                assert original_actor[1] == 2 and not original_actor[6]
                reproduced.add(group)
        else:
            raise AssertionError(group)
        assert extra[key][8] == 2, (group, "bank not restored")
        counts[group] = counts.get(group, 0) + 1
    return counts, reproduced


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--openmsx", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=ROOT / "build/bug-verification")
    parser.add_argument("--only", nargs="*", help="Limit single-fix profiles (all-fixes still runs)")
    args = parser.parse_args()
    source = args.rom.read_bytes()
    verify.source = source
    if hashlib.sha256(source).hexdigest() != SOURCE_SHA256:
        parser.error("Unsupported input ROM")
    catalog = tuple({fix.id: fix for fix in (*CATALOG, *NEW_FIXES)}.values())
    names = [fix.id for fix in NEW_FIXES]
    single_profiles = [fix.id for fix in catalog if fix.extended_helpers]
    profiles = {"original": [], **{name: [name] for name in (args.only if args.only is not None else single_profiles)},
                "all": [fix.id for fix in catalog]}
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    cases, baseline, report = fixtures(), None, {}
    for name, enabled in profiles.items():
        rom, info = (source, {}) if name == "original" else make_selected_rom(source, enabled, catalog=catalog)[:2]
        if name != "original":
            assert len(rom) == 262144 and info["asset_repack"] is None
            assert rom[0x8000:0x20000] == source[0x8000:0x20000]
        path, output = out / f"{name}.rom", out / f"{name}.tsv"
        path.write_bytes(rom)
        run(args.openmsx.resolve(), path, script_for(cases, output, rom, info), out, name)
        rows, _ = read_rows(output, cases)
        extra, sounds = extras(output)
        current = rows, extra, sounds
        if baseline is None:
            baseline = current
        counts, reproduced = verify(cases, baseline, current, set(enabled))
        assert set(names) <= reproduced
        report[name] = dict(rom_sha256=hashlib.sha256(rom).hexdigest(), rom_bytes=len(rom),
                            cases=counts, function_returns=len(rows), original_bugs_reproduced=sorted(reproduced),
                            enabled=enabled)
        print(f"PASS {name}: {len(cases)} cases / {len(rows)} returns", flush=True)
    result = dict(status="passed", scope="arranged original-Z80 function and segment tests", profiles=report,
                  covered_bug_ids=sorted({bug_id for fix in catalog for bug_id in fix.bug_ids}),
                  original_asset_banks_unchanged=True)
    (out / "report.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
