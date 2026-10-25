"""Export only keyboard events and observed game variables, without ROMs."""
from pathlib import Path
import argparse,gzip,hashlib,json,xml.etree.ElementTree as ET
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--recording',type=Path,required=True)
p.add_argument('--trace',type=Path,required=True)
p.add_argument('--out',type=Path,required=True)
p.add_argument('--rom',type=Path,default=Path('build/combined.rom'))
a=p.parse_args()
root=ET.fromstring(gzip.decompress(a.recording.read_bytes()))
snap=root.find('replay/snapshots')
assert len(snap)==1 and snap[0].findtext('scheduler/currentTime/time')=='0' and snap[0].findtext('cpu/z80/regs/pc')=='0'
events=[];end=None
for e in root.find('replay/events'):
 t=int(e.findtext('StateChange/time/time'));kind=e.attrib['type']
 if kind=='EndLog':end=t;continue
 assert kind=='MSXCommandEvent',kind
 tok=[x.text for x in e.findall('tokens/item')]
 if tok[0]=='plug':continue
 assert tok[0]in('keymatrixup','keymatrixdown')and tok[1]=='8'
 events.append([t,int(tok[0]=='keymatrixdown'),int(tok[2])])
assert end is not None
trace=a.trace.read_text(encoding='utf-8')
data=dict(format='vampire-killer-msx-keyboard-v1',rom_bytes=a.rom.stat().st_size,rom_sha256=hashlib.sha256(a.rom.read_bytes()).hexdigest(),initial_time=0,initial_PC=0,master_clock_hz=3579545*960,end_tick=end,keyboard_events=events,trace_tsv=trace,recording_sha256=hashlib.sha256(a.recording.read_bytes()).hexdigest(),contains_ROM=False,contains_emulator_snapshot=False)
a.out.write_bytes(gzip.compress(json.dumps(data,separators=(',',':')).encode(),mtime=0))
print('Exported',len(events),'keyboard events;',len(trace.splitlines())-1,'observations;',a.out.stat().st_size,'bytes')
