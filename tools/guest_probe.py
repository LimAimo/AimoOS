#!/usr/bin/python3
"""Lab-only serial diagnostics; started exclusively with aimo.test=1.

The normal boot command has no control port or diagnostic service. QEMU's
lab harness binds the channel to its own localhost, with no guest TCP server.
"""
import base64,json,os,subprocess,time
os.environ.setdefault('DISPLAY',':0')
os.environ.setdefault('XAUTHORITY','/run/aimo-greeter/Xauthority')
path='/dev/virtio-ports/aimo.test'
while not os.path.exists(path):time.sleep(.2)
with open(path,'r+b',buffering=0) as channel:
    buffer=b''
    while True:
        block=channel.read(65536)
        if not block:time.sleep(.1);continue
        buffer+=block
        while b'\n' in buffer:
            line,buffer=buffer.split(b'\n',1)
            try:
                request=json.loads(line)
                result=subprocess.run(request['argv'],input=base64.b64decode(request.get('stdin','')),capture_output=True,timeout=request.get('timeout',30))
                response={'code':result.returncode,'stdout':base64.b64encode(result.stdout).decode(),'stderr':base64.b64encode(result.stderr).decode()}
            except Exception as exc:response={'error':type(exc).__name__}
            channel.write((json.dumps(response)+'\n').encode())
