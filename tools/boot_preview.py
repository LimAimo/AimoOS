#!/usr/bin/env python3
"""Test production BIOS boot and capture genuine QMP screenshots (no root probe)."""
import argparse,json,os,socket,subprocess,sys,time
from pathlib import Path
from PIL import Image
P=Path(__file__).resolve().parents[1];B=Path(os.environ.get('AIMO_BUILD_DIR',str(P/'build')))
a=argparse.ArgumentParser();a.add_argument('--disk',type=Path,required=True);a.add_argument('--iso',type=Path);a.add_argument('--writable',action='store_true');a.add_argument('--vga',default='vmware');a.add_argument('--port',type=int,default=19091);args=a.parse_args()
command=[str(B/'sysroot/usr/bin/qemu-system-x86_64'),'-L',str(B/'sysroot/usr/share/qemu'),'-accel','tcg,thread=multi','-cpu','max','-smp','4','-m','4096','-vga',args.vga,'-display','none','-usb','-device','usb-tablet','-device','ich9-ahci,id=sata','-drive',f'file={args.disk},if=none,id=root,format={"vmdk" if args.disk.suffix==".vmdk" else "raw"}','-device','ide-hd,drive=root,bus=sata.0','-netdev','user,id=net','-device','e1000,netdev=net,romfile=','-serial',f'file:{B/"preview-boot.log"}','-qmp',f'tcp:127.0.0.1:{args.port},server=on,wait=off']
if not args.writable:command+=['-snapshot']
if args.iso:command+=['-drive',f'file={args.iso},media=cdrom,readonly=on','-boot','d']
log=(B/'preview-qemu.log').open('w');q=subprocess.Popen(['bash',str(P/'scripts/native_env.sh'),*command],stdout=log,stderr=log)
for _ in range(100):
    try:s=socket.create_connection(('127.0.0.1',args.port),timeout=1);break
    except OSError:
        if q.poll() is not None:raise RuntimeError((B/'preview-qemu.log').read_text())
        time.sleep(.1)
s.settimeout(60);f=s.makefile('rb');f.readline()
def execute(name,arguments=None):
    s.sendall((json.dumps({'execute':name,'arguments':arguments or {}})+'\n').encode())
    while True:
        result=json.loads(f.readline())
        if 'return' in result:return result['return']
        if 'error' in result:raise RuntimeError(result['error'])
execute('qmp_capabilities');print(json.dumps({'ready':True,'pid':q.pid}),flush=True)
try:
    for line in sys.stdin:
        item=json.loads(line);action=item['action']
        if action=='shot':
            out=P/'screenshots';out.mkdir(exist_ok=True);png=out/(Path(item['name']).name+'.png');ppm=png.with_suffix('.ppm');execute('screendump',{'filename':str(ppm)});Image.open(ppm).save(png);ppm.unlink();result={'path':str(png),'size':Image.open(png).size}
        elif action=='keys':result=execute('send-key',{'keys':[{'type':'qcode','data':k} for k in item['keys']],'hold-time':100})
        elif action=='click':
            execute('input-send-event',{'events':[{'type':'abs','data':{'axis':'x','value':round(item['x']/item.get('width',1600)*32767)}},{'type':'abs','data':{'axis':'y','value':round(item['y']/item.get('height',900)*32767)}}]})
            execute('input-send-event',{'events':[{'type':'btn','data':{'button':'left','down':True}}]});time.sleep(.15);result=execute('input-send-event',{'events':[{'type':'btn','data':{'button':'left','down':False}}]})
        elif action=='text':
            for c in item['text']:
                keys=(['shift'] if c.isupper() else [])+[c.lower()] if c.isalnum() else {' ':'spc','\n':'ret','-':'minus','_':['shift','minus'],'/':'slash','.':'dot','=':'equal'}.get(c)
                if isinstance(keys,str):keys=[keys]
                if keys:execute('send-key',{'keys':[{'type':'qcode','data':k} for k in keys],'hold-time':70});time.sleep(.25)
            result={}
        elif action=='quit':execute('quit');print('{"done":true}',flush=True);break
        elif action=='qmp':result=execute(item['command'],item.get('arguments'))
        else:raise ValueError(action)
        print(json.dumps(result),flush=True)
finally:
    if q.poll() is None:q.terminate()
    q.wait();log.close()
