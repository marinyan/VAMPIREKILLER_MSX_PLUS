"""trap_attack: original-game correction."""
from fixes.bug_descriptions import bug_fix


def emit(c):
    c.label('trap_attack_clear')
    c.emit('32 20 C4 F5 AF 32 22 C4 32 23 C4 F1 C9','store hurt state / preserve af / clear attack and phase / restore af / ret')


def apply(edit,hook,c):
    hook(0x45C8,'32 20 C4','trap_attack_clear','Cancel the interrupted attack on a new trap hit')


FIX = bug_fix('trap_attack', emit_helpers=emit, apply=apply)
