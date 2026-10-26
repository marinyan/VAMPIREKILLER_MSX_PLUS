"""platform_land: original-game correction."""
from fixes.bug_descriptions import bug_fix


def emit(c):
    c.label('platform_landing_y')
    c.emit('E5 C5','preserve hl and bc across the replacement load')
    c.emit('3A 20 C4 FE 01','ld a,($C420) / cp 1')
    c.jr('platform_landing_choose','z')
    c.emit('FE 05','cp 5')
    c.jr('platform_landing_original','nz')
    c.label('platform_landing_choose')
    c.emit('3A 39 C4 B7','ld a,($C439) / or a')
    c.jr('platform_landing_original','z')
    c.emit('3D 3E 07','dec a / ld a,7')
    c.jr('platform_landing_index','nz')
    c.emit('AF','xor a')
    c.label('platform_landing_index')
    c.emit('21 98 C5','ld hl,$C598')
    c.call(0x4061)
    c.emit('7E B7','ld a,(hl) / or a')
    c.jr('platform_landing_original','z')
    c.emit('23 7E C6 07','inc hl / ld a,(hl) / add a,7')
    c.jr('platform_landing_return')
    c.label('platform_landing_original')
    c.emit('3A 25 C4','ld a,($C425)')
    c.label('platform_landing_return')
    c.emit('C1 E1 C9','restore bc and hl / ret')
    c.label('platform_landing_jump')
    c.call('platform_landing_y')
    c.emit('32 25 C4 21 25 C4 C9','ld ($C425),a / ld hl,$C425 / ret')


def apply(edit,hook,c):
    hook(0x2D3B,'21 25 C4','platform_landing_jump','Align a selected jump landing with its platform surface')
    hook(0x2FF2,'3A 25 C4','platform_landing_y','Align a selected injury landing with its platform surface')


FIX = bug_fix('platform_land', emit_helpers=emit, apply=apply)
