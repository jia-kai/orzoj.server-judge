#!/usr/bin/env python
import socket
import snc, conf

conf.parse_file("test-snc-server.conf")

HOST = ''
PORT = 9351
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind((HOST, PORT))
s.listen(1)
conn, addr = s.accept()
print 'Connected by', addr
ss = snc.Snc(conn, True)
print 'Received: {0!r}' . format(ss.read_str(-1))
ss.write_str("message received.")
ss.close()
conn.close()
s.close()
