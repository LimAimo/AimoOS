#!/usr/bin/env python3
"""Interactive QEMU laboratory. Send one JSON command per stdin line.

QMP input and screendumps come from the real booted virtual machine. Diagnostic
commands use a lab-only virtio channel. All listening sockets bind localhost.
"""
from pathlib import Path
import base64,json,os,socket,subprocess,sys,time
if sys.stdin.isatty():
    import termios
    settings=termios.tcgetattr(sys.stdin.fileno())
    settings[3]&=~(termios.ECHO|termios.ICANON)
    termios.tcsetattr(sys.stdin.fileno(),termios.TCSANOW,settings)
PROJECT=Path(__file__).resolve().parents[1]
OUT=Path(os.environ.get('AIMO_OUT_DIR',str(PROJECT/'out')))
BUILD=Path(os.environ.get('AIMO_BUILD_DIR',str(PROJECT/'build')));SHOT=PROJECT/'screenshots'
SHOT.mkdir(exist_ok=True)
log=(BUILD/'qemu.log').open('w')
command=[str(BUILD/'sysroot/usr/bin/qemu-system-x86_64'),'-L',str(BUILD/'sysroot/usr/share/qemu'),
    '-accel','tcg,thread=multi','-cpu','max','-smp',os.environ.get('AIMO_VM_CPUS','4'),'-m',os.environ.get('AIMO_VM_RAM','4096'),'-usb','-device','usb-tablet',
    '-vga','none','-device','VGA,xres=1600,yres=900','-display','none','-audiodev','none,id=audio','-device','intel-hda','-device','hda-duplex,audiodev=audio',
    '-device','virtio-rng-pci','-netdev','user,id=net0','-device','e1000,netdev=net0,romfile=',
    '-kernel',str(OUT/'vmlinuz'),'-initrd',str(OUT/'initrd.gz'),
    '-append','root=/dev/vda rw console=ttyS0 loglevel=4 aimo.test=1',
    '-drive',f'file={OUT/"aimoos.img"},format=raw,if=virtio',
    '-serial',f'file:{BUILD/"boot.log"}','-qmp','tcp:127.0.0.1:18981,server=on,wait=off',
    '-device','virtio-serial-pci','-chardev','socket,id=probe,host=127.0.0.1,port=18982,server=on,wait=off',
    '-device','virtserialport,chardev=probe,name=aimo.test','-no-reboot']
qemu=subprocess.Popen(command,stdout=log,stderr=log)
def connect(port):
    for _ in range(100):
        if qemu.poll() is not None:raise RuntimeError((BUILD/'qemu.log').read_text())
        try:return socket.create_connection(('127.0.0.1',port),timeout=1)
        except OSError:time.sleep(.1)
    raise TimeoutError('QEMU control unavailable')
qmp=connect(18981);qmp.settimeout(60);qmpfile=qmp.makefile('rb')
qmpfile.readline()
def execute(name,arguments=None):
    qmp.sendall((json.dumps({'execute':name,'arguments':arguments or {}})+'\n').encode())
    while True:
        reply=json.loads(qmpfile.readline())
        if 'return' in reply:return reply['return']
        if 'error' in reply:raise RuntimeError(reply['error'])
execute('qmp_capabilities')
probe=connect(18982);probe.settimeout(65);probefile=probe.makefile('rb')
print(json.dumps({'ready':True,'pid':qemu.pid}),flush=True)
try:
    for line in sys.stdin:
        try:
            item=json.loads(line);action=item.get('action')
            if action=='qmp':result=execute(item['command'],item.get('arguments'))
            elif action=='shot':
                name=Path(item.get('name','screen')).name
                ppm=SHOT/(name+'.ppm');execute('screendump',{'filename':str(ppm)})
                from PIL import Image
                png=SHOT/(name+'.png');Image.open(ppm).save(png);ppm.unlink()
                result={'path':str(png),'size':Image.open(png).size}
            elif action=='keys':result=execute('send-key',{'keys':[{'type':'qcode','data':k} for k in item['keys']],'hold-time':item.get('hold',70)})
            elif action=='text':
                for character in item['text']:
                    if character.isalpha():keys=(['shift'] if character.isupper() else [])+[character.lower()]
                    elif character.isdigit():keys=[character]
                    else:keys={' ':'spc','\n':'ret','-':'minus','.':'dot','/':'slash','_':['shift','minus'],':':['shift','semicolon']}.get(character)
                    if isinstance(keys,str):keys=[keys]
                    if keys:execute('send-key',{'keys':[{'type':'qcode','data':k} for k in keys],'hold-time':35});time.sleep(.065)
                result={}
            elif action=='click':
                x=round(item['x']/item.get('width',1600)*32767);y=round(item['y']/item.get('height',900)*32767)
                execute('input-send-event',{'events':[{'type':'abs','data':{'axis':'x','value':x}},{'type':'abs','data':{'axis':'y','value':y}}]})
                execute('input-send-event',{'events':[{'type':'btn','data':{'button':'left','down':True}}]});time.sleep(.22)
                execute('input-send-event',{'events':[{'type':'btn','data':{'button':'left','down':False}}]});time.sleep(.15);result={}
            elif action=='guest':
                request={key:item[key] for key in ('argv','timeout') if key in item}
                if 'stdin' in item:request['stdin']=base64.b64encode(item['stdin'].encode()).decode()
                probe.sendall((json.dumps(request)+'\n').encode());result=json.loads(probefile.readline())
                for key in ('stdout','stderr'):
                    if key in result:result[key]=base64.b64decode(result[key]).decode('utf-8','replace')
            elif action=='host':
                completed=subprocess.run(item['argv'],capture_output=True,text=True,timeout=item.get('timeout',30))
                result={'code':completed.returncode,'stdout':completed.stdout,'stderr':completed.stderr}
            elif action=='quit':execute('quit');print(json.dumps({'done':True}),flush=True);break
            else:raise ValueError('Unknown laboratory action')
            print(json.dumps({'ok':True,'result':result},ensure_ascii=False),flush=True)
        except Exception as exc:print(json.dumps({'ok':False,'error':str(exc)}),flush=True)
finally:
    if qemu.poll() is None:qemu.terminate()
    qemu.wait();log.close()
