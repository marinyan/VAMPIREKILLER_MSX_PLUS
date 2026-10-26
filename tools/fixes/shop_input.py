"""shop_input: original-game correction."""
from fixes.bug_descriptions import bug_fix


def emit(c):
    c.label('shop_open_sync')
    c.call(0x93FF)
    c.jp(0x951F)


def apply(edit,hook,c):
    hook(0x5387,'CD FF 93','shop_open_sync','Synchronize the held-input baseline on opening a shop window')


FIX = bug_fix('shop_input', emit_helpers=emit, apply=apply)
