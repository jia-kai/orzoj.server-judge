#!/usr/bin/env python

from orzoj.judge import limiter
from orzoj import conf

conf.parse_file("test-limiter.conf")

l = limiter.limiter_dict["default"]

for i in range(2):

    with open("prog.in", "r") as f:
        l.run({"TARGET" : ["./prog", "arg1", "arg2"]}, stdin = f,
                stdout = limiter.SAVE_OUTPUT, stderr = limiter.NULL)

    print "l.stdout={0!r}\nl.stderr={1!r}".format(l.stdout, l.stderr)

    print "execution status:", l.exe_status
    print "time: {0} [sec]" .format(l.exe_time * 1e-6)
    print "mem: {0} [kb]" . format(l.exe_mem)
    print "extra infomation: {0!r}" . format(l.exe_extra_info)


