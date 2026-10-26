"""trap_contact: original-game correction."""
from fixes.bug_descriptions import bug_fix


def emit(c):
    c.label('trap_contact_test')
    c.emit('3A 20 C4 FE 05 C8 FE 06 C9','ld a,($C420) / cp 5 / ret z / cp 6 / ret')


def apply(edit,hook,c):
    hook(0x45A6,'3A 20 C4','trap_contact_test','Reject trap damage while already hurt or dead')
    edit(0x45A9,'FE 06 C8','C8 00 00','Return on either rejected player state')


FIX = bug_fix('trap_contact', emit_helpers=emit, apply=apply)
