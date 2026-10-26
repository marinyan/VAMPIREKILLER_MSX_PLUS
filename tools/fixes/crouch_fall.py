"""crouch_fall: original-game correction."""
from fixes.bug_descriptions import bug_fix


def emit(c):
    c.label('crouch_support')
    c.call(0x85F4)
    c.jr('crouch_support_done','c')
    c.emit('3A 20 C4 FE 02','ld a,($C420) / cp 2')
    c.jr('crouch_support_done','nz')
    c.call(0x7B88)
    c.jr('crouch_support_done','c')
    c.emit('3A 39 C4 B7','ld a,($C439) / or a')
    c.jr('crouch_support_done','nz')
    c.call(0x6BA5)
    c.label('crouch_support_done')
    c.emit('C9','ret')


def apply(edit,hook,c):
    hook(0x2DA9,'CD F4 85','crouch_support','Check support after preserving crouch passage handling')


FIX = bug_fix('crouch_fall', emit_helpers=emit, apply=apply)
