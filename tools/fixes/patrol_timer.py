"""patrol_timer: original-game correction."""
from fixes.bug_descriptions import bug_fix


def emit(c):
    c.label('patrol_timer_refill')
    c.emit('DD 7E 0C B7','ld a,(ix+12) / or a')
    c.jr('patrol_timer_ready','nz')
    c.emit('DD 36 0C 60','ld (ix+12),96')
    c.label('patrol_timer_ready')
    c.emit('DD 34 10 C9','inc (ix+16) / ret')


def apply(edit,hook,c):
    hook(0x660F,'DD 34 10','patrol_timer_refill','Refill an expired patrol timer after priority branches')


FIX = bug_fix('patrol_timer', emit_helpers=emit, apply=apply)
