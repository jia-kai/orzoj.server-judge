# $File: filetrans.py
# $Author: Jiakai <jia.kai66@gmail.com>
# $Date: Tue Sep 14 11:09:25 2010 +0800
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

"""implementation of OFTP (orzoj file transfer protocol)"""

import datetime, hashlib, os.path
import log, msg, snc

_PACKET_SIZE = 1024 * 16
_OFTP_VERSION = 0x0f000001

# orzoj file transfer protocol (OFTP) :
#
# step 0:
#   server and client try to open the file,
#   if successfully, send each other OFTP_BEGIN;
#   otherwise OFTP_SYSTEM_ERROR is sent.
# 
# step 1:
#   server and client send each other
#   OFTP_VERSION, and they must have
#   the same OFTP_VERSION to continue
# 
# step 2:
#   server sends the file size to client,
#   client replies with OFTP_TRANS_BEGIN
# 
# step 3:
#   server sends the file in continuous packets,
#   each of PACKET_SIZE bytes (possibly except for
#   the last one).
# 
# step 4:
#   server and client send each other OFTP_END. 
#   client computes SHA-1 checksum of the received
#   file and sends it back to server,
#   server replies with OFTP_CHECK_OK or OFTP_CHECK_FAIL

class OFTPError(Exception):
    pass

def _td2seconds(td):
    return td.microseconds * 1e-6 + td.seconds + td.days * 24 * 3600

def send(fpath, conn):
    """send the file at @fpath, return the speed in kb/s
    OFTPError may be raised"""

    def _write_msg(m):
        msg.write_msg(conn, m)

    def _read_msg():
        return msg.read_msg(conn)

    def _check_msg(m):
        if m != _read_msg():
            log.warning("message check error.")
            raise OFTPError

    try:
        time_start = datetime.datetime.now()
        sha_ctx = hashlib.sha1()
        fsize = os.path.getsize(fpath)
        with open(fpath, "rb") as fptr:
            _write_msg(msg.OFTP_BEGIN)
            _check_msg(msg.OFTP_BEGIN)
            _write_msg(_OFTP_VERSION)
            if conn.read_uint32() != _OFTP_VERSION:
                log.warning("version check error.")
                raise OFTPError
            conn.write_uint32(fsize)
            _check_msg(msg.OFTP_TRANS_BEGIN)
            
            s = 0
            while s < fsize:
                psize = _PACKET_SIZE
                s += psize
                if s > fsize:
                    psize -= s - fsize
                buf = fptr.read(psize)
                sha_ctx.update(buf)
                conn.write_all(buf)
            _write_msg(msg.OFTP_END)
            _check_msg(msg.OFTP_END)

            if conn.read_all(sha_ctx.digest_size) != sha_ctx.digest():
                _write_msg(msg.OFTP_CHECK_FAIL)
            else:
                _write_msg(msg.OFTP_CHECK_OK)

            return fsize / 1024.0 / _td2seconds(datetime.datetime.now() - time_start)

    except EnvironmentError as e:
        log.error("error while sending file [errno {0}] [filename {1!r}]: {2}" .
                format(e.errno, e.filename, e.strerror))
        conn.write_uint32(msg.OFTP_SYSTEM_ERROR)
        raise OFTPError
    except snc.SncError:
        log.warning("failed to transfer file because of network error.")
        raise OFTPError

def recv(fpath, conn):
    """receive file and save it at @fpath, return the speed in kb/s
    OFTPError may be raised"""

    def _write_msg(m):
        msg.write_msg(conn, m)

    def _read_msg():
        return msg.read_msg(conn)

    def _check_msg(m):
        if m != _read_msg():
            log.warning("message check error.")
            raise OFTPError

    try:
        time_start = datetime.datetime.now()
        sha_ctx = hashlib.sha1()
        with open(fpath, "wb") as fptr:
            _check_msg(msg.OFTP_BEGIN)
            _write_msg(msg.OFTP_BEGIN)
            _write_msg(_OFTP_VERSION)
            if conn.read_uint32() != _OFTP_VERSION:
                log.warning("version check error.")
                raise OFTPError
            fsize = conn.read_uint32()
            _write_msg(msg.OFTP_TRANS_BEGIN)

            s = 0
            while s < fsize:
                psize = _PACKET_SIZE
                s += psize
                if s > fsize:
                    psize -= s - fsize
                buf = conn.read_all(psize)
                sha_ctx.update(buf)
                fptr.write(buf)

            _check_msg(msg.OFTP_END)
            _write_msg(msg.OFTP_END)

            conn.write_all(sha_ctx.digest())
            m = _read_msg()
            if m == msg.OFTP_CHECK_OK:
                return fsize / 1024.0 / _td2seconds(datetime.datetime.now() - time_start)
            else:
                log.warning("SHA1 check failed while receiving file.")
                raise OFTPError

    except EnvironmentError as e:
        log.error("error while receiving file [errno {0}] [filename {1!r}]: {2}" .
                format(e.errno, e.filename, e.strerror))
        conn.write_uint32(msg.OFTP_SYSTEM_ERROR)
        raise OFTPError
    except snc.SncError:
        log.warning("failed to transfer file because of network error.")
        raise OFTPError

