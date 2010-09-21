#!/usr/bin/env python
from orzoj import snc, conf

conf.parse_file("test-snc-client.conf")

HOST = '127.0.0.1'
PORT = 9351


s = snc.socket(HOST, PORT)

ss = snc.snc(s)

ss.write_str(raw_input("Please enter the message:"))
print "Received: {0!r}" . format(ss.read_str())

ss.close()
s.close()

