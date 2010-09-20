# $File: main.py
# $Author: Jiakai <jia.kai66@gmail.com>
# $Date: Sun Sep 19 16:00:34 2010 +0800
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

"""orzoj-judge"""

import socket, sys, optparse, os

from orzoj import log, conf, control, daemon
from orzoj.judge import work

JUDGE_VERSION = 0x00000101
# major(16 bit),minor(8 bit),revision(8 bit)
# if minor number is odd, this is a development version;
# otherwise it's a stable release

_options = None
_pid_file = None
_server_addr = None
_server_port = None


def get_version_str():
    return "{0}.{1}.{2}" . format(JUDGE_VERSION >> 16,
            (JUDGE_VERSION >> 8) & 0xFF, JUDGE_VERSION & 0xFF)

def _parse_opt():
    parser = optparse.OptionParser(
            usage = "usage: %prog [options]",
            version = "%prog {0}\nWritten by jiakai<jia.kai66@gmail.com>" .
            format(get_version_str()))
    parser.add_option("-c", "--config", default = "/etc/orzoj/judge.conf",
            dest = "conf_file", help = "configuration file path [default: %default]")
    parser.add_option("-d", "--no-daemon", default = False, dest = "no_daemon",
            action = "store_true", help = "do not run in daemon mode (always enabled on non-Unix platforms)")
    global _options
    (_options, args) = parser.parse_args()

def run_judge():
    _parse_opt()
    global _options, _server_addr, _server_port, _pid_file

    conf.parse_file(_options.conf_file)

    if not _options.no_daemon and conf.is_unix:
        daemon.daemon_start()

    daemon.pid_start()

    s = None
    for res in socket.getaddrinfo(_server_addr, _server_port, socket.AF_UNSPEC, socket.SOCK_STREAM):
        (af, socktype, proto, canonname, sa) = res
        try:
            s = socket.socket(af, socktype, proto)
        except socket.error as e:
            log.warning("socket error: {0!r}" . format(e))
            s = None
            continue
        try:
            s.connect(sa)
        except socket.error as e:
            log.warning("socket error: {0!r}" . format(e))
            s.close()
            s = None
            continue

        break # successfully connected

    if s is None:
        log.error("faied to connect to orzoj-server at {0!r}:{1!r}" .
                format(_server_addr, _server_port))
        daemon.pid_end()
    
    try:
        work.connect(s)
    except work.Error:
        log.error("error occurred, terminating program")

    daemon.pid_end()

def _ch_server_addr(arg):
    if len(arg) == 1:
        raise conf.UserError("Option {0} must be specified in the configuration file" .
                format(arg[0]))
    if len(arg) != 3:
        raise conf.UserError("Option {0} takes two arguments" . format(arg[0]))
    global _server_addr, _server_port
    _server_addr = arg[1]
    _server_port = int(arg[2])
    if _server_port <= 0 or _server_port > 65535:
        raise conf.UserError("port must be between 0 and 65536")

def _set_umask(arg):
    os.umask(int(arg[1], 8))

conf.register_handler("ServerAddr", _ch_server_addr)
conf.simple_conf_handler("SetUmask", _set_umask, required = False)

