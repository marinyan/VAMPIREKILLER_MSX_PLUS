"""stun_hp: original-game correction."""
from fixes.bug_descriptions import bug_fix


def emit(c):
    c.label('stun_restore_health')
    c.emit('DD 36 0D 01 DD 36 10 08 C9','ld (ix+13),1 / ld (ix+16),8 / ret')


def apply(edit,hook,c):
    hook(0x5AB8,'DD 36 10','stun_restore_health','Restore health only on the surviving type-18 stun branch')
    edit(0x5ABB,'08','00','Pad the replaced four-byte timer instruction')


FIX = bug_fix('stun_hp', emit_helpers=emit, apply=apply)
