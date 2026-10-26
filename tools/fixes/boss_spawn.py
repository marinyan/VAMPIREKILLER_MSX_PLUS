"""boss_spawn: original-game correction."""
from fixes.bug_descriptions import bug_fix


def emit(c):
    c.label('boss_spawn_guard')
    c.emit('21 00 C8 11 80 00 06 07 AF','find one free primary actor record')
    c.label('boss_spawn_actor')
    c.emit('BE','cp (hl)')
    c.jr('boss_spawn_parts','z')
    c.emit('19','add hl,de')
    c.branch(0x10,'boss_spawn_actor','djnz',True)
    c.emit('C9','ret ; retry later')
    c.label('boss_spawn_parts')
    c.emit('21 38 D6 06 0E 0E 08','ld hl,$D638 / ld b,14 / ld c,8')
    c.label('boss_spawn_part')
    c.emit('7E FE E0','ld a,(hl) / cp $E0')
    c.jr('boss_spawn_part_next','nz')
    c.emit('0D','dec c')
    c.jr('boss_spawn_attempt','z')
    c.label('boss_spawn_part_next')
    c.emit('2C 2C 2C 2C','advance SAT entry')
    c.branch(0x10,'boss_spawn_part','djnz',True)
    c.emit('C9','ret ; retry later')
    c.label('boss_spawn_attempt')
    c.emit('11 90 90 0E 13','ld de,$9090 / ld c,$13')
    c.call(0x5F1D)
    c.emit('3A 31 CF B7 C8','ld a,($CF31) / or a / ret z')
    c.emit('21 70 80 01 20 20 AF 16 00','original successful background erase arguments')
    c.call(0x490A)
    c.jp(0xBE3D)


def apply(edit,hook,c):
    hook(0x7CF9,'11 90 90','boss_spawn_guard','Wait for Medusa actor and sprite capacity before spawning',0xC3)
    edit(0x7CFC,'0E 13 CD 1D 5F 21 70 80 01 20 20 3E 00 16 00 CD 0A 49 C3 3D BE',bytes(21),'Advance the boss phase only after a successful spawn')


FIX = bug_fix('boss_spawn', emit_helpers=emit, apply=apply)
