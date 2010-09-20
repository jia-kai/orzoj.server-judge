#!/usr/bin/env python
import socket
import snc, conf, filetrans, sys

if len(sys.argv) != 2:
    sys.exit("usage: %s <file to be sent>" % sys.argv[0])

conf.parse_file("test-snc-client.conf")

HOST = '127.0.0.1'
PORT = 9352

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect((HOST, PORT))
ss = snc.Snc(s)

print "speed: {0}" . format(filetrans.send(sys.argv[1], ss))

ss.close()
s.close()

