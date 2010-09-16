#!/usr/bin/env python
import socket
import snc, conf, filetrans, sys

if len(sys.argv) != 2:
    sys.exit("usage: %s <file saving path>" % sys.argv[0])

conf.parse_file("test-snc-server.conf")

HOST = ''
PORT = 9351
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind((HOST, PORT))
s.listen(1)
conn, addr = s.accept()
print 'Connected by', addr
ss = snc.Snc(conn, True)

print "speed: {0}" . format(filetrans.recv(sys.argv[1], ss))

ss.close()
conn.close()
s.close()
