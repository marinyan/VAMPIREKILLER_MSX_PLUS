"""projectile_box: original-game correction."""
from fixes.bug_descriptions import bug_fix


def emit(c):
    c.label('projectile_two_boxes')
    c.emit('E5 FD 21 50 C4','push hl / ld iy,$C450')
    c.call(0x8500)
    c.jr('projectile_second_box','nc')
    c.emit('33 33 C9','discard saved dimensions without changing result registers / ret')
    c.label('projectile_second_box')
    c.emit('E1 FD 21 60 C4','pop hl / ld iy,$C460')
    c.jp(0x8500)


def apply(edit,hook,c):
    hook(0x44F0,'FD 21 50','projectile_two_boxes','Use the same base dimensions for each projectile slot',0xC3)
    edit(0x44F3,'C4 CD 00 85 D8 FD 21 60 C4 CD 00 85 C9',bytes(13),'Replace the original two-slot dispatcher')


FIX = bug_fix('projectile_box', emit_helpers=emit, apply=apply)
