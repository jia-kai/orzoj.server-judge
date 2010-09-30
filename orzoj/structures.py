# $File: structures.py
# $Author: Jiakai <jia.kai66@gmail.com>
# $Date: Wed Sep 29 23:10:26 2010 +0800
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

"""definition of miscellaneous structures"""

import Queue, threading

class judge:
    def __init__(self):
        self.id = None  # should be assigned a string 
        self.lang_supported = set([])
        self.id_num = None # will be assigned in web.register_new_judge

class task:
    def __init__(self):
        """self.input/self.output: I/O filename, set to empty string to use stdin/stdout"""
        self.id = None  # should be int
        self.prob = None
        self.lang = None
        self.src = None
        self.input = None
        self.output = None
        # all attributes except self.id should be string

(
EXESTS_RIGHT,
EXESTS_PARTIALLY_RIGHT,
EXESTS_WRONG_ANSWER,
EXESTS_TLE,
EXESTS_SIGKILL,
EXESTS_SIGSEGV,
EXESTS_SIGNAL,
EXESTS_ILLEGAL_CALL,  # illegal syscall
EXESTS_EXIT_NONZERO,
EXESTS_SYSTEM_ERROR
) = range(10)

EXECUTION_STATUS_STR = {
    EXESTS_RIGHT : "right",
    EXESTS_PARTIALLY_RIGHT : "partially right",
    EXESTS_WRONG_ANSWER : "wrong answer",
    EXESTS_TLE : "time limit exceeded",
    EXESTS_SIGKILL : "received SIGKILL",
    EXESTS_SIGSEGV : "received SIGSEGV",
    EXESTS_SIGNAL : "terminated by signal",
    EXESTS_ILLEGAL_CALL : "illegal system call",
    EXESTS_EXIT_NONZERO : "non-zero exit code",
    EXESTS_SYSTEM_ERROR : "system error"
}

class case_result:
    def __init__(self):
        self.exe_status = None
        self.score = None
        self.time = None        # microseconds
        self.memory = None      # kb
        self.extra_info = None  # human-readable string
    def write(self, conn, timeout = 0):
        conn.write_uint32(self.exe_status, timeout)
        conn.write_uint32(self.score, timeout)
        conn.write_uint32(self.time, timeout)
        conn.write_uint32(self.memory, timeout)
        conn.write_str(self.extra_info, timeout)
    def read(self, conn, timeout = 0):
        self.exe_status = conn.read_uint32(timeout)
        self.score = conn.read_uint32(timeout)
        self.time = conn.read_uint32(timeout)
        self.memory = conn.read_uint32(timeout)
        self.extra_info = conn.read_str(timeout)

class prob_result:
    def __init__(self):
        self.total_score = 0
        self.full_score = 0
        self.total_time = 0
        self.max_mem = 0
    def write(self, conn, timeout = 0):
        conn.write_uint32(self.total_score)
        conn.write_uint32(self.full_score)
        conn.write_uint32(self.total_time)
        conn.write_uint32(self.max_mem)
    def read(self, conn, timeout = 0):
        self.total_score = conn.read_uint32(timeout)
        self.full_score = conn.read_uint32(timeout)
        self.total_time = conn.read_uint32(timeout)
        self.max_mem = conn.read_uint32(timeout)

