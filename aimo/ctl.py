import os,socket,sys
path=os.environ.get("AIMO_SOCKET_PATH",f"/tmp/aimoos-{os.getuid()}.sock")
with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as connection:
    connection.connect(path);connection.sendall(sys.argv[1].encode())
