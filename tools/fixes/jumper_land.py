"""Keep an unsupported carried jumper in its initial falling phase."""
from fixes.bug_descriptions import bug_fix


def apply(edit, hook, c):
    edit(0x7274, "38 00", "D0 00", "Return without landing when the initial jumper descent has no support")


FIX = bug_fix("jumper_land", apply=apply)
