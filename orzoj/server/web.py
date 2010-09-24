# $File: web.py
# $Author: Jiakai <jia.kai66@gmail.com>
# $Date: Fri Sep 24 00:26:32 2010 +0800
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

"""interface for communicating with orzoj-website

version 1:
    request to web:
        POST data=json.dumps({"thread_id" : int, "req_id" : int, "data" : str, "checksum" : str})  

        where req_id is a strictly increasing integer for each thread
        checksum = sha1sum(str(thread_id) + str(req_id) + sha1sum(_dynamic_passwd + _static_passwd) + data)

    response from web:
        json.dumps({"status" : int, "data" : str, "checksum" : str})
        where status is either 0 or 1, 0 = success, 1 = error (data is a human-readable reason)
        checksum = sha1sum(str(thread_id) + str(req_id) + sha1sum(_dynamic_passwd + _static_passwd) + str(status) + data)

"""

_VERSION = 1
_DYNAMIC_PASSWD_MAXLEN = 128

import urllib2, urllib, sys, hashlib, threading, json

from orzoj import conf, log

_static_passwd = None
_passwd = None
_retry_cnt = None
_timeout = None
_web_addr = None
_thread_req_id = dict()

class _internal_error(Exception):
    def __init__(self, msg):
        self.msg = msg
    def __repr__(self):
        return self.msg

class Error(Exception):
    pass

def report_error(task, msg):
    """send a human-readable error message"""
    pass

def get_query_list():
    """return a list containing the queries for judge info"""
    return []

def register_new_judge(judge, query_ans):
    """register a new judge. @judge should be structures.judge,
    and query_ans should be a dictionary"""
    pass

def remove_judge(judge):
    pass

def fetch_task():
    """try to fetch a new task. return None if no new task available.
    this function does not raise exceptions"""
    return None

def report_no_judge(task):
    """tell the website that no judge supports the task's language
    this function does not raise exceptions"""
    pass

def report_no_data(task):
    """tell the website that there are no data for the task
    this function does not raise exceptions"""

def report_judge_waiting(task):
    """judge is waiting because it's serving another orzoj-server?"""
    pass

def report_compiling(task, judge):
    """now compiling @task on @judge"""
    pass

def report_compile_success(task):
    """successfully compiled"""
    pass

def report_compile_failure(task):
    """failed to compile"""
    pass

def report_case_result(task, result):
    pass

def report_prob_result(task, result):
    pass


def _sha1sum(s):
    return hashlib.sha1(s).hexdigest()

def _read(data, maxlen = None)
    """if @maxlen is not None, data should be dict and is sent via GET method and without checksum
    and return the data read;
    otherwise @data is dumped by json and sent via POST method and return the data read

    Note: @maxlen is not None iff now trying to login
    """
    global _retry_cnt, _web_addr, _thread_req_id, _passwd

    if maxlen:
        url = _web_addr + "?" + urllib.urlencode(data)
    else:
        thread_id = threading.current_thread().ident
        try:
            req_id = _thread_req_id[thread_id]
        except KeyError:
            req_id = 0
        _thread_req_id[thread_id] = req_id + 1
        checksum_base = str(thread_id) + str(req_id) + _passwd
        data = json.dumps(data)
        data_sent = urllib.urlencode("data" :
                json.dumps({"thread_id" : thread_id, "req_id" : req_id, "data" : data,
                    "checksum" : _sha1sum(checksum_base + data)}))

    cnt = _retry_cnt
    if not cnt
        cnt = 1
    while cnt:
        cnt -= 1
        try:
            if maxlen:
                return urllib2.urlopen(url, None, _timeout).read(maxlen)

            ret = urllib2.urlopen(_web_addr, data_sent, _timeout).read()

            ret = json.loads(ret)

            ret_status = ret["status"]
            ret_data = ret["data"]

            if ret["checksum"] != _sha1sum(checksum_base + str(ret_status) + ret_data):
                raise _internal_error("checksum error")

            if int(ret_status):
                raise _internal_error("website says an error happens there: {0}" . format(ret_data))

            return ret_data

        except Exception as e:
            log.error("website communication error: {0!r}" .
                    format(e))
            sys.stderr.write("orzoj-server: website communicating error. See the log for details.\n")
            continue

    raise Error

def _login():
    """
    1. read at most _DYNAMIC_PASSWD_MAXLEN bytes from msg.php?action=login1&version=_VERSION,
       _dynamic_passwd is the data read
       _dynamic_passwd = "0" means version check error
    2. from msg.php?action=login2&checksum=_sha1sum(_sha1sum(_dynamic_passwd + _static_passwd)),
       and verify that it should be _sha1sum(_sha1sum(_dynamic_passwd) + _static_passwd)"""

    global _dynamic_passwd, _static_passwd, _passwd

    try:

        try:
            _dynamic_passwd = _read({"action" : "login1", "version" : _VERSION},  _DYNAMIC_PASSWD_MAXLEN)
            if _dynamic_passwd == '0':
                raise _internal_error("website version check error")

            vpwd = _sha1sum(_sha1sum(_dynamic_passwd) + _static_passwd)
            _passwd = _sha1sum(_dynamic_passwd + _static_passwd)
  
            if (_read({"action" : "login2",
                "checksum" : _sha1sum(_passwd)}, len(vpwd)) != vpwd):
                raise _internal_error("website verification error")

        except Error:
            raise _internal_error("failed to login to the website")

    except _internal_error as e:
        log.error(e.msg)
        sys.exit("orzoj-server: {0}" . format(e.msg))

def _set_static_password(arg):
    global _static_passwd
    _static_passwd = arg[1]

def _set_web_timeout(arg):
    global _timeout
    _timeout = int(arg[1])

def _set_web_addr(arg[1]):
    global _web_addr
    _web_addr = arg[1].rstrip('/') + "msg.php"

conf.simple_conf_handler("Password", _set_static_password)
conf.simple_conf_handler("WebTimeout", _set_web_timeout, "5")
conf.register_init_func(_login)

