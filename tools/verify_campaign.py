"""Independently replay ordinary input from a time-zero openMSX recording."""
from pathlib import Path
import argparse,csv,gzip,hashlib,json,os,re,subprocess,sys,time,xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]

def sha(path):
 return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--recording',type=Path)
 p.add_argument('--baseline',type=Path)
 p.add_argument('--inputs',type=Path)
 p.add_argument('--out',type=Path,required=True)
 p.add_argument('--partial',action='store_true')
 p.add_argument('--rom',type=Path,default=Path('build/combined.rom'))
 p.add_argument('--openmsx',type=Path,default=Path('.local/openmsx/openmsx.exe'))
 a=p.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
 if a.inputs:
  assert a.recording is None and a.baseline is None
  data=json.loads(gzip.decompress(a.inputs.read_bytes()))
  assert data['format']=='vampire-killer-msx-keyboard-v1' and data['initial_time']==0 and data['initial_PC']==0
  assert data['rom_sha256']==sha(a.rom) and data['rom_bytes']==a.rom.stat().st_size==131072
  a.baseline=out/'reference.tsv';a.baseline.write_text(data['trace_tsv'],encoding='utf-8')
  sys.path.insert(0,str(ROOT/'tools'))
  from verify_emulator import run
  seed_path=out/'seed.omr'
  relative=lambda x:os.path.relpath(x,ROOT).replace('\\','/')
  seed_code='''set renderer none
set throttle off
set sound_driver null
set save_settings_on_exit false
set power on
set pause off
after time 0.1 {reverse savereplay -maxnofextrasnapshots 0 @SEED@;exit}
'''.replace('@SEED@',relative(seed_path))
  run(a.openmsx.resolve(),a.rom.resolve(),seed_code,out,'seed')
  seed=gzip.decompress(seed_path.read_bytes()).decode()
  seed_root=ET.fromstring(seed)
  maximum=max(int(e.attrib['id'])for e in seed_root.iter()if e.attrib.get('id','').isdecimal())
  events=ET.Element('events')
  for e in seed_root.find('replay/events'):
   if e.attrib['type']!='EndLog':events.append(e)
  previous=-1
  for tick,down,mask in data['keyboard_events']:
   assert isinstance(tick,int)and tick>=previous and tick<data['end_tick'] and down in(0,1)and isinstance(mask,int)and 0<=mask<=255
   previous=tick;maximum+=1
   e=ET.SubElement(events,'item',id=str(maximum),type='MSXCommandEvent')
   change=ET.SubElement(e,'StateChange');t=ET.SubElement(change,'time');ET.SubElement(t,'time').text=str(tick)
   tokens=ET.SubElement(e,'tokens')
   for text in ('keymatrixdown'if down else'keymatrixup','8',str(mask)):ET.SubElement(tokens,'item').text=text
  maximum+=1;e=ET.SubElement(events,'item',id=str(maximum),type='EndLog')
  change=ET.SubElement(e,'StateChange');t=ET.SubElement(change,'time');ET.SubElement(t,'time').text=str(data['end_tick'])
  i,j=seed.index('<events>'),seed.index('</events>')+len('</events>')
  tail=re.sub(r'<currentTime>\s*<time>\d+</time>\s*</currentTime>',f"<currentTime><time>{data['end_tick']}</time></currentTime>",seed[j:])
  a.recording=out/'inputs.omr';a.recording.write_bytes(gzip.compress((seed[:i]+ET.tostring(events,encoding='unicode')+tail).encode(),mtime=0))
 else:
  assert a.recording is not None and a.baseline is not None,'Supply --inputs or both --recording and --baseline'
 tree=ET.fromstring(gzip.decompress(a.recording.read_bytes()))
 snapshots=tree.find('replay/snapshots')
 assert len(snapshots)==1
 assert snapshots[0].findtext('scheduler/currentTime/time')=='0'
 assert snapshots[0].findtext('cpu/z80/regs/pc')=='0'
 event_types={}
 for e in tree.find('replay/events'):
  kind=e.attrib['type'];event_types[kind]=event_types.get(kind,0)+1
  assert kind in ('MSXCommandEvent','MSXJoyState','EndLog'),kind
  if kind=='MSXCommandEvent':
   tokens=[x.text for x in e.findall('tokens/item')]
   assert tokens[0] in ('keymatrixdown','keymatrixup','plug'),tokens
   if tokens[0].startswith('keymatrix'):assert tokens[1]=='8' and 0<=int(tokens[2])<=255
 with a.baseline.open() as f:limit=sum(1 for _ in f)-1
 assert limit>0
 manifest=json.loads((ROOT/'dist/manifest.json').read_text())['variants']['combined']
 assert sha(a.rom)==manifest['rom_sha256'] and a.rom.stat().st_size==131072
 rom=a.rom.read_bytes();checks='\n'.join('if {[binary encode hex [debug read_block memory %d %d]] ne "%s"} {finish resident-corruption;return}'%(c['address'],c['size'],rom[c['source_offset']:c['source_offset']+c['size']].hex())for c in manifest['ram_chunks'])
 rel=lambda x:os.path.relpath(x,ROOT).replace('\\','/')
 tcl=r'''
set renderer none
set throttle off
set sound_driver null
set save_settings_on_exit false
set power on
set pause off
reverse loadreplay -goto begin -viewonly @RECORDING@
set vk_log [open @OUT@/polls.tsv w]
set vk_ram [open @OUT@/ram-samples.tsv w]
fconfigure $vk_log -buffering line
puts $vk_log "n\ttime\tmode\tphase\tworld\theld\tpressed\tplayer80\tstatus16\tflags16\tboss128\tloop\tR"
set vk_n 0
set vk_started 0
set vk_finished 0
set vk_checks 0
proc finish {reason} {
 global vk_n vk_log vk_ram vk_finished vk_checks
 if {$vk_finished} {return}
 set vk_finished 1
 close $vk_log
 close $vk_ram
 set f [open @OUT@/finish.json w]
 puts $f "{\"reason\":\"$reason\",\"updates\":$vk_n,\"time\":[machine_info time],\"resident_checks\":$vk_checks}"
 close $f
 exit
}
proc vk_observe {} {
 global vk_n vk_log vk_ram vk_started vk_checks
 set mode [peek 0xc000]
 if {$mode==5} {set vk_started 1}
 if {!$vk_started || $mode ni {5 11 12}} {return}
 if {$vk_n%100==0} {@CHECKS@;incr vk_checks;puts $vk_ram "$vk_n\t[binary encode hex [debug read_block memory 0xc000 9344]]"}
 puts $vk_log "$vk_n\t[machine_info time]\t$mode\t[peek 0xc001]\t[binary encode hex [debug read_block memory 0xd000 4]]\t[peek 0xc007]\t[peek 0xc006]\t[binary encode hex [debug read_block memory 0xc420 80]]\t[binary encode hex [debug read_block memory 0xc410 16]]\t[binary encode hex [debug read_block memory 0xc700 16]]\t[binary encode hex [debug read_block memory 0xce00 128]]\t[peek 0xcf34]\t[reg R]"
 incr vk_n
 if {$vk_n>=@LIMIT@} {finish target-reached}
}
debug set_bp 0x414d {} {if {[catch {vk_observe} err]} {set ef [open @OUT@/observer-error.txt w];puts $ef $err;close $ef;finish observer-error}}
after time 6000 {finish game-time-limit}
after realtime 150 {finish host-time-limit}
'''.replace('@OUT@',rel(out)).replace('@RECORDING@',rel(a.recording.resolve())).replace('@LIMIT@',str(limit)).replace('@CHECKS@',checks)
 (out/'replay.tcl').write_text(tcl)
 user=out/'user';user.mkdir()
 env=dict(os.environ,OPENMSX_USER_DATA=rel(user),OPENMSX_SYSTEM_DATA=rel(a.openmsx.resolve().parent/'share'))
 si=subprocess.STARTUPINFO();si.dwFlags|=subprocess.STARTF_USESHOWWINDOW;si.wShowWindow=0
 start=time.monotonic()
 with (out/'emulator.log').open('wb')as log:
  proc=subprocess.Popen([rel(a.openmsx.resolve()),'-machine','C-BIOS_MSX2_JP','-cart',rel(a.rom.resolve()),'-romtype','Konami','-script',rel(out/'replay.tcl')],cwd=ROOT,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=log,startupinfo=si,creationflags=0x08000000)
  try:
   proc.wait(timeout=165)
  except BaseException:
   proc.kill();proc.wait();raise
 assert (out/'finish.json').exists(),(out/'emulator.log').read_text(errors='replace')
 finish=json.loads((out/'finish.json').read_text())
 fields=['n','mode','phase','world','held','pressed','player80','status16','flags16','boss128','loop','R']
 differences=[];areas=set();rooms=set();bosses=set();credits=set();final_boss_phases=set();fall_attack_updates=0;deaths=0;was_dead=False;rows=0;last=None
 with a.baseline.open()as f,(out/'polls.tsv').open()as g:
  want=csv.DictReader(f,delimiter='\t');actual=csv.DictReader(g,delimiter='\t')
  for x,y in zip(want,actual):
   changed={k:[x[k],y[k]]for k in fields if x[k]!=y[k]}
   if abs(float(x['time'])-float(y['time']))>1e-9:changed['time']=[x['time'],y['time']]
   if changed and len(differences)<10:differences.append(dict(index=rows,fields=changed))
   w=bytes.fromhex(y['world']);b=bytes.fromhex(y['boss128'])
   areas.add(w[0]);rooms.add((w[0],w[1]))
   if b[0]in range(1,7) and (b[11] or(b[0]==6 and b[1]>=7)):bosses.add(b[0])
   if b[64] and b[49]:credits.add(b[49])
   if b[0]==6:final_boss_phases.add(b[1])
   player=bytes.fromhex(y['player80'])
   if player[0]==4 and player[2]:fall_attack_updates+=1
   dead=bytes.fromhex(y['status16'])[5]==0 or player[0]==6
   if dead and not was_dead:deaths+=1
   was_dead=dead
   rows+=1;last=y
 final_player=bytes.fromhex(last['player80'])if last else b''
 final_status=bytes.fromhex(last['status16'])if last else b''
 complete=(areas>=set(range(19)) and bosses==set(range(1,7)) and credits>=set(range(1,42)) and last['loop']=='1' and last['world']=='00000000' and final_player[7]>16 and final_status[5]==32)
 matched=rows==limit and not differences and finish['reason']=='target-reached'
 report=dict(status='passed'if matched and (complete or a.partial) else'failed',scope='partial input delivery'if a.partial else'complete campaign replay',completed_campaign=complete,replay_matches_source=matched,rom_bytes=len(rom),rom_sha256=sha(a.rom),recording_sha256=sha(a.recording),source_trace_sha256=sha(a.baseline),replay_trace_sha256=sha(out/'polls.tsv'),updates=rows,compared_fields=fields+['time'],differences=differences,areas=sorted(areas),visited_screens=len(rooms),bosses_defeated=sorted(bosses),credits_seen=sorted(credits),final=last,finish=finish,event_types=event_types,initial_snapshot_time=0,initial_PC=0,initial_snapshot_loads=1,midgame_restores=0,game_RAM_PC_ROM_writes=0,host_seconds=round(time.monotonic()-start,3))
 report['work_RAM_samples']=[dict(index=int(n),sha256=hashlib.sha256(bytes.fromhex(raw)).hexdigest())for n,raw in (line.split()for line in (out/'ram-samples.tsv').read_text().splitlines())]
 report.update(input_archive_sha256=sha(a.inputs)if a.inputs else None,
               fresh_power_on_seed=bool(a.inputs),final_boss_phases=sorted(final_boss_phases),
               falling_with_attack_updates=fall_attack_updates,ordinary_death_sequences=deaths)
 (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps({k:report[k]for k in('status','completed_campaign','replay_matches_source','updates','bosses_defeated','credits_seen','host_seconds')}),flush=True)
 assert report['status']=='passed',differences[:1]

if __name__=='__main__':main()
