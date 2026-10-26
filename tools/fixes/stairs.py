"""stairs: original-game correction."""
from fixes.bug_descriptions import bug_fix


def emit(c):
    c.label('stairs_increment')
    c.emit('34 7E B7', 'inc (hl) / ld a,(hl) / or a')
    c.jr('stairs_count_ready','nz')
    c.emit('3E 08 77','ld a,8 / ld (hl),a')
    c.label('stairs_count_ready')
    c.emit('47 C9','ld b,a / ret')


def apply(edit,hook,c):
    for offset in (0x2E33,0x2E6D,0x2EA5,0x2EE0):
        hook(offset,'34 7E 47','stairs_increment','Keep all four stair counters past their initial-entry exemption')


FIX = bug_fix('stairs', emit_helpers=emit, apply=apply)
