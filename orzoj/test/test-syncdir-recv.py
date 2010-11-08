#!/usr/bin/env python
import sys
from orzoj import snc, conf, sync_dir

if len(sys.argv) != 2:
    sys.exit("usage: %s <file saving path>" % sys.argv[0])

conf.parse_file("test-snc-server.conf")

PORT = 9351
s = snc.socket(None, PORT)
(conn, addr) = s.accept()
print 'Connected by', addr
ss = snc.snc(conn, True)

print "speed: {0}" . format(sync_dir.recv(sys.argv[1], ss))

ss.close()
conn.close()
s.close()

