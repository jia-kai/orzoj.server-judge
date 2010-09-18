#!/usr/bin/env python
import conf
print "testing conf module..."
def f0(args):
    print 'f0 called with: ', args
    print '=' * 20

def f1(args):
    print 'f1 called with: ', args
    print '=' * 20

class Fmsg:
    def __init__(self, msg):
        self.msg = msg
    def work(self, args):
        print ("Fmsg with msg={0!r} called with args={1!r}" .
        format(self.msg, args))
        print '=' * 20

def string(arg):
    print "string called with arg={0!r}" . format(arg)
    print '=' * 20

def hd_int(arg):
    print "hd_int called with arg={0!r}" . format(arg)
    x = int(arg[1])
    if x < 0:
        raise conf.UserError("must >= 0")
    print '=' * 20

def init():
    print "init() called"
    print '=' * 20

conf.register_handler('test', f0)
conf.register_handler('testmsg', Fmsg('hello').work)
conf.register_handler('test-default-args', f1)
conf.simple_conf_handler("string", string, "default string")
conf.simple_conf_handler("int", hd_int, "0")
conf.register_init_func(init)

def dup(arg):
    pass

conf.simple_conf_handler("no-dup", dup, no_dup = True)

conf.parse_file("test-conf.conf")

