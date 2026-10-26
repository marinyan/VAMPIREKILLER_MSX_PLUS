"""empty_projectile: original-game correction."""
from fixes.bug_descriptions import bug_fix


def emit(c):
    c.label('projectile_rectangle')
    c.emit('3E 06 85 6F FD 7E 00 B7 C8','expand horizontal radius / reject phase zero')
    c.emit('FD 7E 01 D6 02 FE 04 D0','accept only types 2..5 / ret nc')
    if 'screen_edges' in c.enabled:
        c.emit('FD 7E 01 FE 02','ld a,(iy+1) / cp 2')
        c.jr('projectile_rectangle_position','nz')
        c.emit('FD 7E 0D B7 C0','reject a sword whose X wrapped / carry clear')
    c.label('projectile_rectangle_position')
    c.emit('FD 7E 05 92','ld a,(iy+5) / sub d')
    c.jr('projectile_rectangle_abs','nc')
    c.emit('ED 44','neg')
    c.label('projectile_rectangle_abs')
    c.emit('BD D0 FD 7E 01 FE 02 06 0C','cp l / ret nc / choose original vertical extent')
    c.jr('projectile_rectangle_height','nz')
    c.emit('06 06','ld b,6')
    c.label('projectile_rectangle_height')
    c.emit('4C 78 84 67 FD 7E 04 93 81 BC C9','original vertical interval comparison / ret')


def apply(edit,hook,c):
    hook(0x4500,'3E 06 85','projectile_rectangle','Reject invalid slots after the original horizontal expansion',0xC3)
    edit(0x4503,'6F FD 7E 05 92 30 02 ED 44 BD D0 FD 7E 01 FE 02 06 0C 20 02 06 06 4C 78 84 67 FD 7E 04 93 81 BC C9',bytes(33),'Replace the original projectile rectangle routine')


FIX = bug_fix('empty_projectile', emit_helpers=emit, apply=apply)
