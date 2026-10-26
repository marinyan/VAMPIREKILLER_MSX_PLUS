"""Rollback only sprite bindings created by the current failed allocation."""


def emit_rollback(c):
    if "allocation_rollback" in c.labels:
        return
    c.label("allocation_rollback")
    c.emit("F5 C5 D5 E5 43 78 B7", "preserve af/bc/de/hl / ld b,e / ld a,b / or a")
    c.jr("allocation_rollback_done", "z")
    c.emit("DD E5 E1 11 21 00 19", "push ix / pop hl / ld de,33 / add hl,de")
    c.label("allocation_rollback_next")
    c.emit("7E E5 87 87 C6 38 6F 26 D6 36 E0 E1 11 05 00 19",
           "read binding index / free its SAT entry / advance descriptor by five bytes")
    c.branch(0x10, "allocation_rollback_next", "djnz", True)
    c.label("allocation_rollback_done")
    c.emit("E1 D1 C1 F1 C9", "restore hl/de/bc/af / ret")
