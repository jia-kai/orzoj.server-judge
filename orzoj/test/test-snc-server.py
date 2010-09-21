#!/usr/bin/env python
from orzoj import snc, conf

conf.parse_file("test-snc-server.conf")

PORT = 9351
s = snc.socket(None, PORT)
(conn, addr) = s.accept(5)
print 'Connected by', addr
ss = snc.snc(conn, True)
print 'Received: {0!r}' . format(ss.read_str())
ss.write_str("message received.")
ss.close()
conn.close()
s.close()

