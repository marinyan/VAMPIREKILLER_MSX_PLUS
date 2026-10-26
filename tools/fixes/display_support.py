"""Original linear/rotated SAT layout shared by the display improvements."""


def emit(c):
    c.label("display_restore_sat")
    c.emit("3A 0C CE B7", "special boss presentation uses the linear SAT")
    c.jr("display_restore_linear", "nz")
    c.emit("3A 00 CE FE 05", "Death also keeps linear priority")
    c.jr("display_restore_linear", "z")
    c.emit("3A AC C5 FE 05", "special door presentation")
    c.jr("display_restore_linear", "z")
    c.emit("3A 07 00 4F CD 70 65 C9", "restore with the current pair rotation, without advancing it")
    c.label("display_restore_linear")
    c.emit("CD A4 65 C9", "restore the original contiguous colors and SAT")

    c.label("display_sat_pair")
    c.emit("D5 5F 3A 0C CE B7", "preserve de / remember logical pair / special presentation")
    c.jr("display_pair_linear", "nz")
    c.emit("3A 00 CE FE 05", "Death")
    c.jr("display_pair_linear", "z")
    c.emit("3A AC C5 FE 05", "special door")
    c.jr("display_pair_linear", "z")
    c.emit("3A 0F C0 0F 0F 0F E6 0F 57 7B 92 5F 87 87 87 83 E6 0F 07 07 07 D1 C9",
           "invert original pair rotation: ((logical-start)*9)&15, then times8 / restore de / ret")
    c.label("display_pair_linear")
    c.emit("7B 07 07 07 D1 C9", "logical pair times8 / restore de / ret")
