# $File: sync_dir.py
# $Author: Jiakai <jia.kai66@gmail.com>
# $Date: Mon Nov 08 09:56:18 2010 +0800
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

"""synchronize a directory"""

class Error(Exception):
    pass

import os, os.path, hashlib, threading, tempfile, tarfile, traceback
from orzoj import filetrans, log, snc, msg

# during directory synchronizing, msg.TELL_ONLINE may be sent
# when busy computing something

class _thread_get_file_list(threading.Thread):
    def __init__(self, path, return_list = True):
        """@return_list: whether to return the result as list of tuple(<filename>, <checksum>)
        or dict(<filename> => <checksum>)
        self.result would be the requested result, or None on error"""
        threading.Thread.__init__(self)
        self.result = None # public, and should not be modified
        self._path = path
        self._ret_list = return_list

    def run(self):
        def _sha1_file(path):
            with open(path, 'rb') as f:
                sha1_ctx = hashlib.sha1()
                while True:
                    buf = f.read(sha1_ctx.block_size)
                    if not buf:
                        return sha1_ctx.digest()
                    sha1_ctx.update(buf)

        try:
            rlist = self._ret_list
            path = self._path
            if rlist:
                ret = list()
            else:
                ret = dict()
            for i in os.listdir(path):
                pf = os.path.join(path, i)
                if os.path.isfile(pf):
                    checksum = _sha1_file(pf)
                    if rlist:
                        tmp = (i, checksum)
                        ret.append(tmp)
                    else:
                        ret[i] = checksum
            self.result = ret
                
        except OSError as e:
            log.error("failed to obtain file list of {0!r}: [errno {1}] [filename {2!r}]: {3}" .
                    format(path, e.errno, e.filename, e.strerror))
        except Exception as e:
            log.error("failed to obtain file list of {0!r}: {1!r}" .
                    format(path, e))

class _thread_make_tar(threading.Thread):
    def __init__ (self, fobj, dirpath, flist):
        threading.Thread.__init__(self)
        self._fobj = fobj
        self._dirpath = dirpath
        self._flist = flist
        self.error = False

    def run(self):
        try:
            tf = tarfile.open(mode = 'w:gz', fileobj = self._fobj, dereference = True)
            for f in self._flist:
                tf.add(os.path.join(self._dirpath, f), f)
            tf.close()
        except Exception as e:
            log.error("failed to create tar file: {0!r}" . format(e))
            self.error = True

class _thread_extract_tar(threading.Thread):
    def __init__(self, fobj, dirpath):
        threading.Thread.__init__(self)
        self._fobj = fobj
        self._dirpath = dirpath
        self.error = False

    def run(self):
        try:
            tf = tarfile.open(mode = "r", fileobj = self._fobj)
            tf.extractall(self._dirpath)
            tf.close()
        except Exception as e:
            log.error("failed to extract tar file: {0!r}" . format(e))
            self.error = True

def send(path, conn):
    """send the directory at @path via snc connection @conn,
    return the speed in kb/s, or None if no file transferred"""

    def _write_msg(m):
        msg.write_msg(conn, m)

    def _write_str(s):
        conn.write_str(s)

    def _write_uint32(v):
        conn.write_uint32(v)

    def _read_msg():
        return msg.read_msg(conn)

    def _read_str():
        return conn.read_str()

    def _read_uint32():
        return conn.read_uint32()

    def _check_msg(m):
        while True:
            m1 = _read_msg()
            if m1 == msg.TELL_ONLINE:
                continue
            if m1 != m:
                log.warning("message check error: expecting {0}, got {1}" .
                        format(m, m1))
                raise Error
            return

    flist = _thread_get_file_list(path)
    flist.start()
    while flist.is_alive():
        flist.join(msg.TELL_ONLINE_INTERVAL)
        _write_msg(msg.TELL_ONLINE)
    flist = flist.result
    if flist is None:
        raise Error

    try:
        _write_msg(msg.SYNCDIR_BEGIN)
        _write_uint32(len(flist))
        for i in flist:
            _write_str(i[0])
            _write_str(i[1])

        _check_msg(msg.SYNCDIR_FILELIST)

        nfile = _read_uint32()
        if nfile == 0:
            _check_msg(msg.SYNCDIR_DONE)
            return None

        flist_req = list()
        while nfile:
            nfile -= 1
            flist_req.append(flist[_read_uint32()][0])

        ftar = tempfile.mkstemp('orzoj')

        try:
            with open(ftar[1], 'wb') as f:
                th_mktar = _thread_make_tar(f, path, flist_req)
                th_mktar.start()
                while th_mktar.is_alive():
                    th_mktar.join(msg.TELL_ONLINE_INTERVAL)
                    _write_msg(msg.TELL_ONLINE)
                if th_mktar.error:
                    raise Error

            _write_msg(msg.SYNCDIR_FTRANS)
            speed = filetrans.send(ftar[1], conn)
            _check_msg(msg.SYNCDIR_DONE)
            return speed

        finally:

            os.close(ftar[0])
            os.remove(ftar[1])


    except Error as e:
        raise e

    except snc.Error:
        log.warning("network error while synchronizing directory")
        raise Error

    except filetrans.OFTPError:
        log.warning("failed to transfer file while synchronizing directory")
        raise Error

    except Exception as e:
        log.error("failed to synchronize directory: {0!r}" . format(e))
        log.debug(traceback.format_exc())
        raise Error


def recv(path, conn):
    """save the directory to @path via snc connection @conn,
    return the speed in kb/s, or None if no file transferred"""
    def _write_msg(m):
        msg.write_msg(conn, m)

    def _write_str(s):
        conn.write_str(s)

    def _write_uint32(v):
        conn.write_uint32(v)

    def _read_msg():
        return msg.read_msg(conn)

    def _read_str():
        return conn.read_str()

    def _read_uint32():
        return conn.read_uint32()

    def _check_msg(m):
        while True:
            m1 = _read_msg()
            if m1 == msg.TELL_ONLINE:
                continue
            if m1 != m:
                log.warning("message check error: expecting {0}, got {1}" .
                        format(m, m1))
                raise Error
            return

    try:
        if os.path.isdir(path):
            th_hash = _thread_get_file_list(path, False)
            th_hash.start()
            while th_hash.is_alive():
                th_hash.join(msg.TELL_ONLINE_INTERVAL)
                _write_msg(msg.TELL_ONLINE)
            flist_local = th_hash.result
        else:
            if os.path.exists(path):
                os.remove(path)
            os.mkdir(path)
            flist_local = dict()
        if flist_local is None:
            raise Error

        flist_needed = list()
        _check_msg(msg.SYNCDIR_BEGIN)
        
        for i in range(_read_uint32()):
            fname = _read_str()
            checksum = _read_str()
            try:
                if checksum != flist_local[fname]:
                    os.remove(os.path.join(path, fname))
                    flist_needed.append(i)
                del flist_local[fname]
            except KeyError:
                flist_needed.append(i)

        for i in flist_local:
            os.remove(os.path.join(path, i))

        _write_msg(msg.SYNCDIR_FILELIST)
        _write_uint32(len(flist_needed))

        if len(flist_needed) == 0:
            _write_msg(msg.SYNCDIR_DONE)
            return None

        for i in flist_needed:
            _write_uint32(i)

        _check_msg(msg.SYNCDIR_FTRANS)

        try:
            ftar = tempfile.mkstemp('orzoj')
            speed = filetrans.recv(ftar[1], conn)
            with open(ftar[1], 'r') as f:
                th_extar = _thread_extract_tar(f, path)
                th_extar.start()
                while th_extar.is_alive():
                    th_extar.join(msg.TELL_ONLINE_INTERVAL)
                    _write_msg(msg.TELL_ONLINE)
                if th_extar.error:
                    raise Error
            _write_msg(msg.SYNCDIR_DONE)
            return speed

        finally:
            os.close(ftar[0])
            os.remove(ftar[1])

    except Error as e:
        raise e

    except snc.Error:
        log.warning("network error while synchronizing directory")
        raise Error

    except filetrans.OFTPError:
        log.warning("failed to transfer file while synchronizing directory")
        raise Error

    except Exception as e:
        log.error("failed to synchronize directory: {0!r}" . format(e))
        log.debug(traceback.format_exc())
        raise Error


