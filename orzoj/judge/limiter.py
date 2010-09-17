# $File: limiter.py
# $Author: Jiakai <jia.kai66@gmail.com>
# $Date: Fri Sep 17 20:00:41 2010 +0800
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
"""parse limiter configuration and export functions to use limiter"""

import subprocess, socket, tempfile, struct, os, platform, sys, time

from orzoj import conf, log

limiter_dict = {}

class SysError(Exception):
    def __init__(self, msg):
        self.msg = msg

class _empty_class:
    pass

SAVE_OUTPUT = _empty_class()

_LIMITER_SOCKET = 0
_LIMITER_FILE = 1

try:
    if platform.system() == 'Windows':
        NULL = open('nul', 'w')
    else:
        NULL = open('/dev/null', 'w')
except Exception as e:
    sys.exit("faied to open NULL device: {0!r}", NULL)

class _Limiter:
    def __init__(self, args):
        if len(args) < 3:
            raise conf.UserError("Option AddLimiter takes at least three arguments")

        self._name = args[0]

        if args[1] == 'socket':
            self._type = _LIMITER_SOCKET
        elif args[1] == 'file':
            self._type = _LIMITER_FILE
        else:
            raise conf.UserError("unknown limiter communication method: {0!r}" .
                    format(args[1]))
        self._args = args[2:]

        global limiter_dict
        if args[0] in limiter_dict:
            raise conf.UserError("duplicated limiter name: {0!r}" . format(args[0]))
        limiter_dict[args[0]] = self

    def run(self, var_dict, stdin = None, stdout = None, stderr = None):
        """run the limiter under variables defined in @var_dict
        
        execution result can be accessed via self.exe_status, self.exe_time (in microseconds),
        self.exe_mem (in kb) and self.exe_extra_info

        if @stdout and/or @stderr is SAVE_OUTPUT, stdout and/or stderr will be stored
        in self.stdout and self.stderr
        """

        self.stdout = None
        self.stderr = None

        if self._type == _LIMITER_SOCKET:
            try:
                socket_name = "orzoj-limiter-socket.{0}.{1}" . format(
                        os.getpid(), time.time()) # use pid and time to avoid conflicting

                s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                s.bind("\0{0}".format(socket_name))
                s.listen(1)
                trans_dict = {"SOCKNAME" : socket_name} # dict for variable for transfer data
            except Exception as e:
                log.error("[limiter {0!r}] failed to establish socket: {1!r}" .
                        format(self._name, e))
                raise SysError("limiter socket error")
        else:
            try:
                ftmp = tempfile.mkstemp()
                trans_dict = {"FILENAME" : ftmp[1]}
            except Exception as e:
                log.error("[limiter {0!r}] failed to create temporary file: {1!r}" .
                        format(self._name, e))
                raise SysError("limiter socket error")


        def _eval(s):
            if s[0] != '$':
                return s
            try:
                return str(eval(s[1:], trans_dict, var_dict))
            except Exception as e:
                log.error("[limiter {0!r}] error while evaluating argument {1!r}: {2!r}" .
                        format(self._name, s, e))
                raise SysError("limiter configuration error")

        args = [_eval(i) for i in self._args]

        log.debug("executing command: {0!r}" . format(args))

        try:
            stdout_ = stdout
            if stdout_ is SAVE_OUTPUT:
                stdout_ = subprocess.PIPE
            stderr_ = stderr
            if stderr_ is SAVE_OUTPUT:
                stderr_ = subprocess.PIPE
            p = subprocess.Popen(args, stdin = stdin, stdout = stdout_, stderr = stderr_)
        except OSError as e:
            log.error("error while calling Popen [errno {0}] "
                    "[filename {1!r}]: {2}" . format(e.errno, e.filename, e.strerror))
            raise SysError("failed to execute limiter")
        except Exception as e:
            log.error("error while calling Popen: {0!r}" .  format(e))
            raise SysError("failed to execute limiter")

        if self._type == _LIMITER_SOCKET:
            try:
                s.settimeout(1)
                (conn, addr) = s.accept()
                (self.exe_status, self.exe_time, self.exe_mem, info_len) = \
                        struct.unpack("IIII", conn.recv(16))
                if info_len:
                    self.exe_extra_info = conn.recv(info_len)
                else:
                    self.exe_extra_info = ''
            except socket.timeout:
                log.error("[limiter {0!r}] socket timed out" .
                        format(self._name))
                raise SysError("limiter socket error")
            except Exception as e:
                log.error("[limiter {0!r}] failed to retrieve data through socket: {1!r}" .
                        format(self._name, e))
                raise SysError("limiter socket error")

        if stdout is SAVE_OUTPUT or stderr is SAVE_OUTPUT:
            (self.stdout, self.stderr) = p.communicate()
        else:
            p.wait()

        if self._type == _LIMITER_FILE:
            try:
                with os.fdopen(ftmp[0], 'rb') as f:
                    (self.exe_status, self.exe_time, self.exe_mem, info_len) = \
                            struct.unpack("IIII", f.read(16))
                    if info_len:
                        self.exe_extra_info = f.read(info_len)
                    else:
                        self.exe_extra_info = ''
                os.close(ftmp[0])
                os.remove(ftmp[1])
            except Exception as e:
                log.error("[limiter {0!r}] failed to retrieve data through file: {1!r}" .
                        format(self._name, e))
                raise SysError("limiter socket error")

        if self._type == _LIMITER_SOCKET:
            try:
                conn.close()
                s.close()
            except Exception as e:
                log.warning("failed to close socket: {0!r}".format(e))

def _ch_add_limiter(arg):
    if arg is None:
        raise UserError("Option AddLimiter must be specified in the configuration file.")
    _Limiter(arg)

conf.register_handler("AddLimiter", _ch_add_limiter)

