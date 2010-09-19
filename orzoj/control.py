# $File: control.py
# $Author: Jiakai <jia.kai66@gmail.com>
# $Date: Sun Sep 19 10:22:35 2010 +0800
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

"""make the program execution controllable by the user"""

import threading, signal
import log

_termination_flag = False
_lock = threading.Lock()


def test_termination_flag():
    global _termination_flag, _lock
    with _lock:
        return _termination_flag

def set_termination_flag():
    global _termination_flag, _lock
    with _lock:
        _termination_flag = True

def sig_handler(signum, frame):
    set_termination_flag()
    log.info("reveived signal {0!r}, terminating..." .
            format(signum))

signal.signal(signal.SIGTERM, sig_handler)
signal.signal(signal.SIGINT, sig_handler)

