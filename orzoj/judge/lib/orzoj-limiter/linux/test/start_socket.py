#!/usr/bin/env python
import socket, struct

s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
s.bind("\0orzoj-limiter")
s.listen(1)
(conn, addr) = s.accept()
(exe_status, time, memory, info_len) = struct.unpack("IIII", conn.recv(16))
if not info_len:
    info = ''
else:
    info = conn.recv(info_len);
print "execution status:", exe_status
print "time: {0} [sec]" .format( time * 1e-6)
print "mem: {0} [kb]" .format(memory)
print "extra infomation: {0!r}" . format(info)

conn.close()
s.close()

