"""mummy_start: original-game correction."""
from fixes.bug_descriptions import bug_fix


def emit(c):
    c.label('mummy_zero_velocity')
    c.call(0xA55D)
    c.jp(0xA56C)


def apply(edit,hook,c):
    hook(0x7887,'CD 5D A5','mummy_zero_velocity','Initialize both mummy velocity components')


FIX = bug_fix('mummy_start', emit_helpers=emit, apply=apply)
