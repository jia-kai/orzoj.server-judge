# $File: main.py
# $Author: Jiakai <jia.kai66@gmail.com>
# $Date: Sun Sep 19 16:48:44 2010 +0800
#
# This file is part of orzoj
# 
# Copyright (C) <2010>  Jiakai <jia.kai66@gmail.com>
# 
# Orzoj is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# Orzoj is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with orzoj.  If not, see <http://www.gnu.org/licenses/>.
#

"""orzoj-server"""

import socket, sys, optparse, time, threading, os
from orzoj import log, conf, control, daemon
from orzoj.server import work

SERVER_VERSION = 0x00000101
# major(16 bit),minor(8 bit),revision(8 bit)
# if minor number is odd, this is a development version;
# otherwise it's a stable release

_options = None
_use_ipv6 = False
_port = None

def get_version_str():
    return "{0}.{1}.{2}" . format(SERVER_VERSION >> 16,
            (SERVER_VERSION >> 8) & 0xFF, SERVER_VERSION & 0xFF)

def _parse_opt():
    parser = optparse.OptionParser(
            usage = "usage: %prog [options]",
            version = "%prog {0}\nWritten by jiakai<jia.kai66@gmail.com>" .
            format(get_version_str()))
    parser.add_option("-c", "--config", default = "/etc/orzoj/server.conf",
            dest = "conf_file", help = "configuration file path [default: %default]")
    parser.add_option("-d", "--no-daemon", default = False, dest = "no_daemon",
            action = "store_true", help = "do not run in daemon mode (always enabled on non-Unix platforms)")
    global _options
    (_options, args) = parser.parse_args()

def run_server():
    _parse_opt()
    global _options, _use_ipv6, _port
    conf.parse_file(_options.conf_file)

    if not _options.no_daemon and conf.is_unix:
        daemon.daemon_start()

    daemon.pid_start()

    try:
        if _use_ipv6:
            s = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        else:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(('', _port))
        s.listen(5)
    except socket.error as e:
        log.error("socket error: {0!r}" . format(e))
        daemon.pid_end()
        sys.exit(1)

    log.info("orzoj-server started, listening on {0}" .
            format(_port))

    threading.Thread(target = work.thread_work, name = "work.thread_work").start()

    while not control.test_termination_flag():
        try:
            (conn, addr) = s.accept()
        except socket.error as e:
            log.error("socket error: {0!r}" . format(e))
            control.set_termination_flag()
            break

        log.info("connected by {0!r}" . format(addr))
        work.thread_new_judge_connection(conn).start()

    s.close()
    while threading.active_count() > 1:
        log.debug("waiting for threads, current active count: {0}" .
                format(threading.active_count()))
        for i in threading.enumerate():
            log.debug("active thread: {0!r}" . format(i.name))
        time.sleep(1)

    log.info("all threads ended, program exiting")

    daemon.pid_end()


def _ch_set_ipv6(arg):
    if len(arg) > 2 or (len(arg) == 2 and arg[1]):
        raise conf.UserError("Option UseIPv6 takes no argument")
    if len(arg) == 2:
        global _use_ipv6
        _use_ipv6 = True

def _set_port(arg):
    global _port
    _port = int(arg[1])
    if _port <= 0 or _port > 65535:
        raise conf.UserError("port must be between 0 and 65536")

conf.register_handler("UseIPv6", _ch_set_ipv6)
conf.simple_conf_handler("Listen", _set_port)

