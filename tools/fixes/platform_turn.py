"""platform_turn: original-game correction."""
from fixes.bug_descriptions import bug_fix


def emit(c):
    c.label('platform_carry')
    c.emit('3D 3E 07','dec a / ld a,7')
    c.jr('platform_carry_index','nz')
    c.emit('AF','xor a')
    c.label('platform_carry_index')
    c.emit('21 98 C5','ld hl,$C598')
    c.call(0x4061)
    c.emit('E5 2C 2C 2C 2C 2C 2C 7E 3C 2D 2D BE E1 C8','compare counter+1 to period / restore platform pointer / ret z')
    c.emit('23 23 23 7E 17 16 00','select original direction / ld d,0')
    c.jr('platform_carry_left','c')
    c.call(0x7BA9)
    c.emit('D8 16 01','ret c / ld d,1')
    c.jr('platform_carry_move')
    c.label('platform_carry_left')
    c.call(0x7C05)
    c.emit('D8 16 FF','ret c / ld d,-1')
    c.label('platform_carry_move')
    c.emit('3A 27 C4 82 32 27 C4 C9','ld a,($C427) / add a,d / ld ($C427),a / ret')


def apply(edit,hook,c):
    hook(0x2BAF,'3D 3E 07','platform_carry','Do not carry the player on a stationary platform reversal',0xC3)
    edit(0x2BB2,'20 01 AF 21 98 C5 CD 61 40 23 23 23 7E 17 16 00 38 08 CD A9 7B D8 16 01 18 06 CD 05 7C D8 16 FF 3A 27 C4 82 32 27 C4 C9',bytes(40),'Replace the original moving-platform carry routine')


FIX = bug_fix('platform_turn', emit_helpers=emit, apply=apply)
