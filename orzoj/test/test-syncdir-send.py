#!/usr/bin/env python
import sys
from orzoj import snc, conf, sync_dir

if len(sys.argv) != 2:
    sys.exit("usage: %s <directory to be sent>" % sys.argv[0])

conf.parse_file("test-snc-client.conf")

HOST = '127.0.0.1'
PORT = 9351

s = snc.socket(HOST, PORT)

ss = snc.snc(s)

print "speed: {0}" . format(sync_dir.send(sys.argv[1], ss))

ss.close()
s.close()

