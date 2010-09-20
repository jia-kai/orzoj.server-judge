# $File: snc.py
# $Author: Jiakai <jia.kai66@gmail.com>
# $Date: Sun Sep 19 19:38:03 2010 +0800
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

import ssl, socket, struct

import conf, log

_timeout    = None
_cert_file  = None
_key_file   = None
_ca_file    = None

class Error(Exception):
    pass

class Snc:
    """secure network connection, a wrapper for python ssl module

    Error may be raised by any method
    Key method arguments:
            timeout -- the timeout set on reading and writing, expressing in seconds,
                       besides default timeout. Setting it to a negative value disables timeouts.
    """
    def __init__(self, sock, is_server = False):
        global _cert_file, _key_file, _ca_file
        try:
            self._closed = True
            self._ssl = ssl.wrap_socket(sock, keyfile = _key_file,
                    certfile = _cert_file, ca_certs = _ca_file,
                    server_side = is_server, cert_reqs = ssl.CERT_REQUIRED,
                    ssl_version = ssl.PROTOCOL_TLSv1)
            self._closed = False  # now successfully initialized
        except socket.timeout:
            log.error("socket timeout")
            raise Error
        except socket.error as e:
            log.error("socket error: {0!r}" . format(e))
            raise Error
        except ssl.SSLError as e:
            log.error("SSLError: {0!r}" . format(e))
            raise Error

    def _set_timeout(self, val):
        global _timeout
        if val < 0:
            slef._ssl.settimeout(None)
        else:
            self._ssl.settimeout(val)

    def read_all(self, count, timeout = 0):
        """read repeatedly until @count bytes are read"""
        try:
            self._set_timeout(timeout)
            ret = ''
            while len(ret) < count:
                ret += self._ssl.read(count - len(ret))
            return ret
        except socket.timeout:
            log.error("socket timeout")
            raise Error
        except socket.error as e:
            log.error("socket error: {0!r}" . format(e))
            raise Error
        except ssl.SSLError as e:
            log.error("SSLError: {0!r}" . format(e))
            raise Error

    def write_all(self, data, timeout = 0):
        """write repeatedly until all data are writen"""
        try:
            self._set_timeout(timeout)
            tot = 0
            while tot < len(data):
                tot += self._ssl.write(data[tot:])
        except socket.timeout:
            log.error("socket timeout")
            raise Error
        except socket.error as e:
            log.error("socket error: {0!r}" . format(e))
            raise Error
        except ssl.SSLError as e:
            log.error("SSLError: {0!r}" . format(e))
            raise Error

    def read_int32(self, timeout = 0):
        """read a signed 32-bit integer and return it"""
        return struct.unpack("!i", self.read_all(4, timeout))[0]

    def write_int32(self, val, timeout = 0):
        """write a signed 32-bit integer"""
        self.write_all(struct.pack("!i", val), timeout)

    def read_uint32(self, timeout = 0):
        """read an unsigned 32-bit integer and return it"""
        return struct.unpack("!I", self.read_all(4, timeout))[0]

    def write_uint32(self, val, timeout = 0):
        """write an unsigned 32-bit integer"""
        self.write_all(struct.pack("!I", val), timeout)

    def read_str(self, timeout = 0):
        """read a string and return it"""
        length = self.read_uint32(timeout)
        return self.read_all(length, timeout)

    def write_str(self, data, timeout = 0):
        """write a string"""
        self.write_uint32(len(data), timeout)
        self.write_all(data, timeout)

    def close(self):
        try:
            if not self._closed:
                self._ssl.unwrap()
                self._closed = True
        except ssl.SSLError as e:
            log.error("SSLError: {0!r}" . format(e))
        except socket.error as e:
            log.error("socket error: {0!r}" . format(e))
        except socket.timeout:
            log.error("socket timeout")

    def __del__(self):
        self.close()



def _init():
    if struct.calcsize("i") != 4 or struct.calcsize("I") != 4:
        sys.exit("standard size of integer or unsigned integer is not 4-byte!")

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

conf.simple_conf_handler("NetworkTimeout", _set_timeout, default = "2")
conf.simple_conf_handler("CertificateFile", _set_cert_file)
conf.simple_conf_handler("PrivateKeyFile", _set_key_file)
conf.simple_conf_handler("CAFile", _set_ca_file)
conf.register_init_func(_init)
