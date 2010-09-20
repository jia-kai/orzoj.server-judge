#!/usr/bin/env python
import socket
import snc, conf

conf.parse_file("test-snc-client.conf")

HOST = '192.168.1.104'
PORT = 9351

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect((HOST, PORT))
ss = snc.Snc(s)

ss.write_str(raw_input("Please enter the message:"))
print "Received: {0!r}" . format(ss.read_str())

ss.close()
s.close()

