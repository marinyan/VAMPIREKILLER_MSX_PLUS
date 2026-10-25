"""Capture a naturally spawned zombie entering the left edge in openMSX.

Only ordinary keyboard input drives the game. Debug reads select the frame;
the screenshot is the emulator's raw PNG, without cropping or compositing.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os

from verify_emulator import run

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, default=ROOT / "build/combined.rom")
    parser.add_argument("--openmsx", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=ROOT / "build/screenshot")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    out = args.out.resolve()
    script = r'''
set renderer SDLGL-PP
set minframeskip 0
set maxframeskip 0
set throttle off
set sound_driver null
set save_settings_on_exit false
set power on
set pause off
set vk_capture_count 0
set vk_capture_frames 0
set vk_capture_positioned 0
set vk_capture_log [open {LOG} w]
fconfigure $vk_capture_log -buffering line
proc vk_edge_frame {} {
 global vk_capture_count vk_capture_frames vk_capture_log vk_capture_positioned
 incr vk_capture_frames
 if {!$vk_capture_positioned && [peek 0xc000] == 5 && [peek 0xd000] == 1 && [peek 0xd001] == 0 && [peek 0xc427] >= 120 && [peek 0xc427] < 180} {
  keymatrixup 8 0x80
  keymatrixdown 8 0x10
  after time 0.08 {keymatrixup 8 0x10}
  set vk_capture_positioned 1
 }
 if {$vk_capture_positioned && [peek 0xc000] == 5} {
  for {set slot 0} {$slot < 7} {incr slot} {
   set address [expr {0xc800 + 128*$slot}]
   set x [peek [expr {$address+5}]]
   set sprite_slot [peek [expr {$address+33}]]
   if {[peek $address] == 1 && $x <= 4 && $sprite_slot<18 && ([peek [expr {0xd4e0+16*$sprite_slot}]] & 128)} {
    set file [format {DIRECTORY/zombie-left-%02d.png} $vk_capture_count]
    screenshot -raw -size 640 $file
    puts $vk_capture_log "$vk_capture_count\t[machine_info time]\t$vk_capture_frames\t$slot\t$x\t[binary encode hex [debug read_block memory $address 128]]\t[binary encode hex [debug read_block memory 0xd638 72]]\t[binary encode hex [debug read_block memory 0xd4e0 288]]"
    incr vk_capture_count
    if {$vk_capture_count >= 2} {close $vk_capture_log;exit;return}
   }
  }
 }
 after frame vk_edge_frame
}
after frame vk_edge_frame
after time 13 {keymatrixdown 8 1}
after time 13.5 {keymatrixup 8 1}
after time 23.5 {keymatrixdown 8 0x80}
after time 36 {set throttle on}
after time 100 {puts $vk_capture_log "TIMEOUT\t[machine_info time]";close $vk_capture_log;exit}
after realtime 45 {puts $vk_capture_log "TIMEOUT\t[machine_info time]";close $vk_capture_log;exit}
'''.replace("LOG", os.path.relpath(out / "captures.tsv", ROOT).replace("\\", "/"))
    script = script.replace("DIRECTORY", os.path.relpath(out, ROOT).replace("\\", "/"))
    run(args.openmsx.resolve(), args.rom.resolve(), script, out, "zombie-edge")
    rows = [line.split("\t") for line in (out / "captures.tsv").read_text().splitlines()]
    frames = []
    for row in rows:
        if row[0] == "TIMEOUT":
            break
        index, time, frame, slot, x = row[:5]
        path = out / f"zombie-left-{int(index):02d}.png"
        if not path.is_file():
            raise RuntimeError(f"Missing screenshot: {path.name}")
        actor = bytes.fromhex(row[5])
        assert actor[0] == 1 and actor[5] <= 4
        frames.append(dict(file=path.name, emulated_time=float(time), frame=int(frame),
                           slot=int(slot), center_x=int(x), actor_hex=row[5],
                           sat_hex=row[6], colors_hex=row[7],
                           png_sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    if not frames:
        raise RuntimeError("No naturally spawned zombie was captured at the left edge")
    evidence = dict(rom_sha256=hashlib.sha256(args.rom.read_bytes()).hexdigest(),
                    method="ordinary keyboard input from power-on; read-only frame selection; raw emulator screenshot",
                    frames=frames)
    (out / "capture.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(f"Captured {len(frames)} frames; first zombie center X={frames[0]['center_x']}")


if __name__ == "__main__":
    main()
