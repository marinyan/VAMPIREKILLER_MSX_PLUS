"""hourglass: original-game correction."""
from fixes.bug_descriptions import bug_fix


def emit(c):
    c.label('hourglass_area_clear')
    c.emit('F5 21 10 D0 CB 46','push af / ld hl,$D010 / bit 0,(hl)')
    c.jr('hourglass_area_ready','z')
    c.emit('CB 86 3E FC','res 0,(hl) / ld a,$FC')
    c.call(0x509F)
    c.label('hourglass_area_ready')
    c.emit('F1 21 20 C4 C9','pop af / ld hl,$C420 / ret')


def apply(edit,hook,c):
    hook(0x23B7,'21 20 C4','hourglass_area_clear','End a stopwatch effect before area player-state clearing')


FIX = bug_fix('hourglass', emit_helpers=emit, apply=apply)
