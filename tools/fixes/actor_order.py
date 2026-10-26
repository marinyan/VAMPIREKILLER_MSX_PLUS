"""Visit each original actor once, keeping returned-child postprocessing."""
from fixes.bug_descriptions import bug_fix


def emit(c):
    c.label("actor_order_loop")
    c.emit("C5", "preserve caller C; original loop returns B=0")
    c.call("actor_live_mask")
    c.emit("5F 16 00 01 01 07 DD 21 00 C8", "e=live / d=deferred / b=7 / c=current bit / ix=first owner")
    c.label("actor_order_next")
    c.emit("79 A3", "current owner must have been live after the preceding step")
    c.jr("actor_order_advance", "z")
    c.emit("79 A2", "do not dispatch a newborn's AI again in this scan")
    c.jr("actor_order_advance", "nz")
    c.emit("C5 D5 DD E5", "save scan state and original owner")
    c.call(0x992F)
    c.jr("actor_order_edge", "c")
    c.call(0x993B)
    c.call(0x99B9)
    c.label("actor_order_edge")
    c.call(0x99E5)
    c.emit("DD E1 D1 C1", "restore owner only after returned-child movement and edge processing")
    c.call("actor_live_mask")
    c.emit("6F 7B 2F A5 B2 57 5D", "l=next / deferred |= next & ~live / live=next")
    c.label("actor_order_advance")
    c.emit("D5 11 80 00 DD 19 D1 CB 21", "advance original owner while preserving scan masks / shift current bit")
    c.branch(0x10, "actor_order_next", "djnz", True)
    c.emit("C1 06 00 C9", "restore caller C / b=0 / ret")

    c.label("actor_live_mask")
    c.emit("DD E5 C5 D5 E5 DD 21 00 C8 11 80 00 21 00 01 06 07", "save registers / ix=first / de=stride / h=bit / l=mask / b=7")
    c.label("actor_mask_next")
    c.emit("DD 7E 00 B7", "test owner type")
    c.jr("actor_mask_empty", "z")
    c.emit("7D B4 6F", "mask |= bit")
    c.label("actor_mask_empty")
    c.emit("DD 19 CB 24", "next record and bit")
    c.branch(0x10, "actor_mask_next", "djnz", True)
    c.emit("7D E1 D1 C1 DD E1 C9", "return live mask in a; restore scan registers")


def apply(edit, hook, c):
    hook(0x58EC, "DD 21 00", "actor_order_loop", "Keep actor scan owners monotonic while retaining newborn postprocessing", opcode=0xC3)


FIX = bug_fix("actor_order", emit_helpers=emit, apply=apply)
