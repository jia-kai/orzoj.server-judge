# $File: work.py
# $Author: Jiakai <jia.kai66@gmail.com>
# $Date: Tue Sep 21 17:15:23 2010 +0800
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

import platform, os, os.path, hashlib, threading, time

from orzoj import msg, snc, conf, log, control, filetrans
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


_file_list = None
def _get_file_list(path):
    """set _file_list a dict containing regular files and their corresponding sha1 digests in the direcory @path.
    _file_list will be None on error"""
    def _sha1_file(path):
        with open(path, 'rb') as f:
            sha1_ctx = hashlib.sha1()
            while True:
                buf = f.read(sha1_ctx.block_size)
                if not buf:
                    return sha1_ctx.digest()
                sha1_ctx.update(buf)

    global _file_list

    try:
        _file_list = dict()
        for i in os.listdir(path):
            pf = os.path.normpath(os.path.join(path, i))
            if os.path.isfile():
                _file_list[i] = _sha1_file(pf)
            
    except OSError as e:
        log.error("failed to obtain file list of {0!r}: [errno {1}] [filename {2!r}]: {3}" .
                format(path, e.errno, e.filename, e.strerror))
        _file_list = None
    except Exception as e:
        log.error("failed to obtain file list of {0!r}: {1!r}" .
                format(path, e))
        _file_list = None

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

        while not control.test_termination_flag():
            m = _read_msg()

            if m == msg.TELL_ONLINE:
                continue

            if m == msg.ERROR:
                log.warning("failed to work: orzoj-server says an error happens there`")
                raise Error

            if m == msg.QUERY_INFO:
                global _info_dict
                q = _read_str()
                _write_msg(msg.ANS_QEURY)
                try:
                    _write_str(_info_dict[q])
                except KeyError:
                    _write_str("unknown")
                continue

            if m != msg.PREPARE_DATA:
                log.error("unexpected message from orzoj-server: {0}" .  format(m))
                raise Error

            pcode = _read_str()
            cnt = _read_uint32()
            tlist = dict()
            while cnt:
                cnt -= 1
                fname = _read_str()
                tlist[fname] = _read_str()

            try:
                if os.path.exists(pcode):
                    if not os.path.isdir(pcode):
                        os.remove(pcode)
                        os.mkdir(pcode)
                else:
                    os.mkdir(pcode)

                th_hash = threading.Thread(target = _get_file_list, args = (pcode))

                while th_hash.is_alive():
                    _write_msg(msg.DATA_COMPUTING_SHA1)
                    time.sleep(0.5)

                global _file_list
                if _file_list is None:
                    _write_msg(msg.DATA_ERROR)
                    _write_str("failed to list data directory")
                    raise Error

                for (tfname, thash) in tlist.iteritems():
                    if tfname not in _file_list or thash != _file_list[tfname]:
                        _write_msg(msg.NEED_FILE)
                        _write_str(tfname)
                        speed = filetrans.recv(os.path.join(pcode, tfname), snc)
                        log.info("file transfer speed with orzoj-server: {0}" .
                                format(speed))

                for lfname in _file_list:
                    if lfname not in tlist:
                        os.remove(os.path.join(pcode, lfname))

                pconf = probconf.Prob_conf(pcode)

            except filetrans.OFTPError:
                raise Error
            except Error:
                raise
            except snc.Error:
                raise Error
            except probconf.Error:
                _write_msg(msg.DATA_ERROR)
                _write_str("failed to analyse problem configuration (please contact the administrator to view log)")
                raise Error
            except Exception as e:
                log.error("failed to transfer data for problem {0!r}: {1!r}" .
                        format(pcode, e))
                _write_msg(msg.DATA_ERROR)
                _write_str("unexpected error (please contact the administrator to view log)")
                raise Error

            _write_msg(msg.DATA_OK)
            _write_uint32(len(pconf.case))
            for case in pconf.case:
                _write_uint32(case.time)

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

