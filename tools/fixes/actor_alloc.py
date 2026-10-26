"""actor_alloc: original-game correction."""
from fixes.bug_descriptions import bug_fix


from fixes.allocation_support import emit_rollback

def emit(c):
    emit_rollback(c)
    c.label('actor_alloc_run')
    c.emit('11 00 00 21 38 D6 06 0E','ld de,0 / ld hl,$D638 / ld b,14')
    c.label('actor_alloc_next')
    c.emit('7E FE E0','ld a,(hl) / cp $E0')
    c.jr('actor_alloc_skip','nz')
    c.emit('36 E1','ld (hl),$E1')
    c.call(0x6048)
    c.emit('1C 0D','inc e / dec c')
    c.jr('actor_alloc_success','z')
    c.label('actor_alloc_skip')
    c.emit('14 2C 2C 2C 2C','inc d / advance SAT entry')
    c.branch(0x10,'actor_alloc_next','djnz',True)
    c.jp('allocation_rollback')
    c.label('actor_alloc_success')
    c.jp(0x5F77)


def apply(edit,hook,c):
    hook(0x1F59,'11 00 00','actor_alloc_run','Allocate actor sprites with rollback on partial failure',0xC3)
    edit(0x1F5C,'21 38 D6 06 0E 7E FE E0 20 09 36 E1 CD 48 60 1C 0D 28 08 14 2C 2C 2C 2C 10 EB C9',bytes(27),'Replace the original actor allocation loop')


FIX = bug_fix('actor_alloc', emit_helpers=emit, apply=apply)
