# $File: daemon.py
# $Author: Jiakai <jia.kai66@gmail.com>
# $Date: Tue Nov 09 08:46:24 2010 +0800
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

"""provide a function that enables current program to run as a daemon (Unix only)
and maintain pid files"""

import os, sys, signal

from orzoj import conf

_pid_file = None

def daemon_start():
    try:
        pid = os.fork()
    except OSError as e:
        sys.exit("orzoj: failed to fork [errno {0}]: {1}" .
                format(e.errno, e.strerror))

    if pid == 0:  # the first child
        os.setsid()
        signal.signal(signal.SIGHUP, signal.SIG_IGN)

        try:
            pid = os.fork()
        except OSError as e:
            sys.exit("orzoj: failed to fork [errno {0}]: {1}" .
                    format(e.errno, e.strerror))

        if pid == 0: # the second child
            os.umask(0)
        else:
            os._exit(0)

    else:
        os._exit(0)

def pid_start():
    if _pid_file:
        try:
            with open(_pid_file, "w") as f:
                f.write("{0}\n" . format(os.getpid()))
        except IOError as e:
            sys.exit("orzoj: failed to open pid file [errno {0}] [filename {1!r}]: {2}" .
                    format(e.errno, e.filename, e.strerror))


def pid_end():
    if _pid_file:
        try:
            os.remove(_pid_file)
        except Exception as e:
            sys.exit("orzoj: faield to remove pid file: {0}" .
                    format(e))

    sys.exit("orzoj: program exited")

def _set_pid_file(arg):
    global _pid_file
    _pid_file = arg[1]

conf.simple_conf_handler("PidFile", _set_pid_file)

