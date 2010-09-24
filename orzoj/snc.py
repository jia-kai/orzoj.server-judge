# $File: snc.py
# $Author: Jiakai <jia.kai66@gmail.com>
# $Date: Thu Sep 23 17:29:16 2010 +0800
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

"""a wrapper for _snc module"""

from orzoj import _snc, log, conf

import struct

_timeout    = None
_cert_file  = None
_key_file   = None
_ca_file    = None


class Error(Exception):
    pass

class ErrorTimeout(Exception):
    pass

_use_ipv6 = 0

def socket(host, port, timeout = 0):
    """set @host to None if in server mode (accept() usable)

    @timeout is only usable in client mode (connection timeout)"""
    try:
        return _socket_real(_snc.socket(host, port, _use_ipv6, timeout), host is None)
    except _snc.error_timeout:
        raise ErrorTimeout
    except Exception as e:
        log.error("socket error: {0!r}" . format(e))
        raise Error

class _socket_real:
    def __init__(self, _socket, _is_server):
        self._socket = _socket
        self._is_server = _is_server

    def __del__(self):
        self.close()

    def accept(self, timeout = 0):
        """return a tuple (conn, addr),
        where conn is a socket instance and addr is a string represeting the peer's address
        only available in server mode
        
        if timeout <= 0, it will block as long as necessary;\
        otherwise it blocks at most @timeout seconds, and then raise Error"""
        if not self._is_server:
            return
        try:
            ret = self._socket.accept(timeout)
            return (_socket_real(ret[0], False), ret[1])
        except _snc.error_timeout:
            raise ErrorTimeout
        except Exception as e:
            log.error("socket error: {0!r}" . format(e))
            raise Error

    def close(self):
        if self._socket:
            self._socket.close()
            self._socket = None


class snc:
    def __init__(self, sock, is_server = 0):
        self._snc = None
        try:
            if is_server:
                is_server = 1
            self._snc = _snc.snc(sock._socket, is_server, _timeout,
                    _cert_file, _key_file, _ca_file)
        except Exception as e:
            log.error("failed to establish SSL connection:\n{0!r}" . format(e))
            raise Error

    def __del__(self):
        self.close()

    def read(self, len, timeout = 0):
        """read exactly @len bytes
        if @timeout is negative, it will block until data available;
        else timeout is @timeout plus @_timeout """
        if timeout < 0:
            timeout = 0
        else:
            timeout += _timeout

        try:
            return self._snc.read(len, timeout)
        except Exception as e:
            log.error("failed to read:\n{0!r}" . format(e))
            raise Error

    def write(self, data, timeout = 0):
        """write all of @data"""
        if timeout < 0:
            timeout = 0
        else:
            timeout += _timeout

        try:
            return self._snc.write(data, timeout)
        except Exception as e:
            log.error("failed to write:\n{0!r}" . format(e))
            raise Error

    def read_int32(self, timeout = 0):
        """read a signed 32-bit integer and return it"""
        return struct.unpack("!i", self.read(4, timeout))[0]

    def write_int32(self, val, timeout = 0):
        """write a signed 32-bit integer"""
        self.write(struct.pack("!i", val), timeout)

    def read_uint32(self, timeout = 0):
        """read an unsigned 32-bit integer and return it"""
        return struct.unpack("!I", self.read(4, timeout))[0]

    def write_uint32(self, val, timeout = 0):
        """write an unsigned 32-bit integer"""
        self.write(struct.pack("!I", val), timeout)

    def read_str(self, timeout = 0):
        """read a string and return it"""
        len = self.read_uint32(timeout)
        return self.read(len, timeout)

    def write_str(self, data, timeout = 0):
        """write a string"""
        self.write_uint32(len(data), timeout)
        self.write(data, timeout)

    def close(self):
        if self._snc:
            self._snc.shutdown()
            self._snc = None


def _ch_set_ipv6(arg):
    if len(arg) > 2 or (len(arg) == 2 and arg[1]):
        raise conf.UserError("Option UseIPv6 takes no argument")
    if len(arg) == 2:
        global _use_ipv6
        _use_ipv6 = 1

def _set_timeout(arg):
    global _timeout
    _timeout = float(arg[1])
    if _timeout <= 1:
        raise conf.UserError("Option {0} can not be less than 1 second." .
                format(arg[0]))

def _set_cert_file(arg):
    global _cert_file
    _cert_file = arg[1]

def _set_key_file(arg):
    global _key_file
    _key_file = arg[1]

def _set_ca_file(arg):
    global _ca_file
    _ca_file = arg[1]

conf.register_handler("UseIPv6", _ch_set_ipv6)
conf.simple_conf_handler("NetworkTimeout", _set_timeout, default = "30")
conf.simple_conf_handler("CertificateFile", _set_cert_file)
conf.simple_conf_handler("PrivateKeyFile", _set_key_file)
conf.simple_conf_handler("CAFile", _set_ca_file)


def _init():
    if struct.calcsize("i") != 4 or struct.calcsize("I") != 4:
        sys.exit("standard size of integer or unsigned integer is not 4-byte!")

conf.register_init_func(_init)

