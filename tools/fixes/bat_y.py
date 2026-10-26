"""Use the bat's Y component in the ceiling-bat descent comparison."""
from fixes.bug_descriptions import bug_fix


def apply(edit, hook, c):
    edit(0x7143, "05", "03", "Compare player height with bat Y instead of bat X")


FIX = bug_fix("bat_y", apply=apply)
