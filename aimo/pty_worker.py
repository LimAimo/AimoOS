#!/usr/bin/env python3
"""PTY fork lives in this single-threaded helper, never in the Qt process."""
import base64,fcntl,json,os,pty,selectors,signal,struct,sys,termios

child,master=pty.fork()
if child==0:
    os.environ["TERM"]="xterm-256color"
    os.environ["PS1"]="\\u@\\h:\\w\\$ "
    os.execvp("bash",["bash","--noprofile","--norc","-i"])
selector=selectors.DefaultSelector();selector.register(master,selectors.EVENT_READ)
selector.register(sys.stdin.fileno(),selectors.EVENT_READ);buffer=b""
try:
    while True:
        for key,_ in selector.select():
            if key.fd==master:
                try:data=os.read(master,65536)
                except OSError:raise SystemExit
                if not data:raise SystemExit
                os.write(sys.stdout.fileno(),data)
            else:
                data=os.read(sys.stdin.fileno(),65536)
                if not data:raise SystemExit
                buffer+=data
                while b"\n" in buffer:
                    line,buffer=buffer.split(b"\n",1);message=json.loads(line)
                    if "data" in message:os.write(master,base64.b64decode(message["data"]))
                    elif "resize" in message:
                        columns,rows=message["resize"]
                        fcntl.ioctl(master,termios.TIOCSWINSZ,struct.pack("HHHH",rows,columns,0,0))
                        os.kill(child,signal.SIGWINCH)
finally:
    try:os.kill(child,signal.SIGHUP)
    except ProcessLookupError:pass
    os.close(master)
