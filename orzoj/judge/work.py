# $File: work.py
# $Author: Jiakai <jia.kai66@gmail.com>
# $Date: Tue Nov 09 11:08:59 2010 +0800
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

"""connect to orzoj-server and wait for tasks"""

import platform, os, os.path, traceback

from orzoj import msg, snc, conf, log, control, sync_dir
from orzoj.judge import core, probconf

_judge_id = None

_info_dict = {
    "platform" : platform.platform()
}

try:
    with open("/proc/cpuinfo", "r") as f:
        _info_dict["cpuinfo"] = f.read()
    with open("/proc/meminfo", "r") as f:
        _info_dict["meminfo"] = f.read()
except:
    pass

class Error(Exception):
    pass


def connect(sock):
    """connect to orzoj-server via socket @sock
    
    may raise Error"""

    def _write_msg(m):
        msg.write_msg(conn, m)

    def _write_str(s):
        conn.write_str(s)

    def _write_uint32(v):
        conn.write_uint32(v)

    def _read_msg(timeout = 0):
        return msg.read_msg(conn, timeout)

    def _read_str():
        return conn.read_str()

    def _read_uint32():
        return conn.read_uint32()

    def _check_msg(m):
        if m != _read_msg():
            log.error("message check error.")
            raise Error
    try:
        conn = snc.snc(sock)

        _write_msg(msg.HELLO)
        global _judge_id
        _write_str(_judge_id)
        _write_uint32(msg.PROTOCOL_VERSION)
        _write_uint32(len(core.lang_dict))
        for i in core.lang_dict:
            _write_str(i)

        m = _read_msg()
        if m == msg.ERROR:
            log.warning("failed to connect: orzoj-server says an error happens there`")
            raise Error

        if m == msg.DUPLICATED_ID:
            log.error("failed to connect: duplicated id: {0!r}" . format(_judge_id))
            raise Error

        if m == msg.ID_TOO_LONG:
            log.error("failed to connect: id {0!r} is too long for the orzoj-server" .
                    format(_judge_id))
            raise Error

        if m != msg.CONNECT_OK:
            log.error("unexpected message from orzoj-server: {0}" .
                    format(m))
            raise Error

        log.info('connection established')

        while not control.test_termination_flag():
            m = _read_msg()

            if m == msg.TELL_ONLINE:
                continue

            if m == msg.ERROR:
                log.warning("failed to work: orzoj-server says an error happens there")
                raise Error

            if m == msg.QUERY_INFO:
                global _info_dict
                q = _read_str()
                _write_msg(msg.ANS_QUERY)
                try:
                    _write_str(_info_dict[q])
                except KeyError:
                    _write_str("unknown")
                continue

            if m != msg.PREPARE_DATA:
                log.error("unexpected message from orzoj-server: {0}" .  format(m))
                raise Error

            pcode = _read_str()
            log.info("received task for problem {0!r}" . format(pcode))
            try:
                speed = sync_dir.recv(pcode, conn)
                if speed:
                    log.info("file transfer speed: {0!r}" . format(speed))

            except sync_dir.Error:
                log.error("failed to synchronize data for problem {0!r}" . format(pcode))
                raise Error

            try:
                pconf = probconf.Prob_conf(pcode)
            except Exception as e:
                errmsg = "failed to parse problem configuration: {0}" . format(e)
                _write_msg(msg.DATA_ERROR)
                _write_str(errmsg)
                log.error(errmsg)
                log.debug(traceback.format_exc())
                continue

            _write_msg(msg.DATA_OK)
            _write_uint32(len(pconf.case))

            _check_msg(msg.START_JUDGE)
            lang = _read_str()
            src = _read_str()
            input = _read_str()
            output = _read_str()

            core.lang_dict[lang].judge(conn, pcode, pconf, src, input, output)

    except snc.Error as e:
        log.error("failed to communicate with orzoj-server because of network error")
        control.set_termination_flag()
        raise Error

    except core.Error:
        control.set_termination_flag()
        raise Error

def _set_datacache(arg):
    os.chdir(arg[1])

def _set_id(arg):
    global _judge_id
    _judge_id = arg[1]

def _ch_set_info(arg):
    if len(arg) == 1:
        return
    if len(arg) < 3:
        raise conf.UserError("Option {0} takes at least two arguments" . format(arg[0]))
    global _info_dict
    _info_dict[arg[1]] = "\n".join(arg[2:])

conf.simple_conf_handler("DataCache", _set_datacache)
conf.simple_conf_handler("JudgeId", _set_id)
conf.register_handler("SetInfo", _ch_set_info)

