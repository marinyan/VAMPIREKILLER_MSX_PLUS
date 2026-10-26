"""projectile_alloc: original-game correction."""
from fixes.bug_descriptions import bug_fix


from fixes.allocation_support import emit_rollback

def emit(c):
    emit_rollback(c)
    c.label('projectile_alloc_run')
    c.label('projectile_alloc_next')
    c.emit('7E FE E0','ld a,(hl) / cp $E0')
    c.jr('projectile_alloc_skip','nz')
    c.emit('36 E1','ld (hl),$E1')
    c.call(0x6048)
    c.emit('1C 0D','inc e / dec c')
    c.jr('projectile_alloc_success','z')
    c.label('projectile_alloc_skip')
    c.emit('15 2D 2D 2D 2D','dec d / retreat SAT entry')
    c.branch(0x10,'projectile_alloc_next','djnz',True)
    c.jp('allocation_rollback')
    c.label('projectile_alloc_success')
    c.jp(0x9FE0)


def apply(edit,hook,c):
    hook(0x5FCA,'7E FE E0','projectile_alloc_run','Allocate projectile sprites with rollback on partial failure',0xC3)
    edit(0x5FCD,'20 09 36 E1 CD 48 60 1C 0D 28 08 15 2D 2D 2D 2D 10 EB C9',bytes(19),'Replace the original projectile allocation loop')


FIX = bug_fix('projectile_alloc', emit_helpers=emit, apply=apply)
