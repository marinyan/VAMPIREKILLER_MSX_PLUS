"""reform_hp: original-game correction."""
from fixes.bug_descriptions import bug_fix


def emit(c):
    c.label('reform_restore_health')
    c.emit('DD 36 0D 02','ld (ix+13),2')
    c.jp(0xB048)


def apply(edit,hook,c):
    hook(0x5AAE,'CD 48 B0','reform_restore_health','Restore health only on the surviving type-09 reform branch')


FIX = bug_fix('reform_hp', emit_helpers=emit, apply=apply)
