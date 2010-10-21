# $File: web.py
# $Author: Jiakai <jia.kai66@gmail.com>
# $Date: Thu Oct 21 18:53:31 2010 +0800
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

sched_work:
    request on orz.php?sched_work
    return "0" for success, otherwise a human readable string describing the error

version 1:
    request to web:
        POST data=json.dumps({"thread_id" : int, 
            "data" : str (json encoded), "checksum" : str})  

        checksum = sha1sum(str(thread_id) + str(req_id) + sha1sum(_dynamic_passwd + _static_passwd) + data)
        where req_id is an integer increasing by 1 per post for each thread

    response from web:
        json.dumps({"status" : int, "data" : str (json encoded), "checksum" : str})
        where status is either 0 or 1, 0 = success, 1 = error (data is a human-readable reason)
        checksum = sha1sum(str(thread_id) + str(req_id) + sha1sum(_dynamic_passwd + _static_passwd) + str(status) + data)

    website can send 'relogin' for reeusting a new login

"""

_VERSION = 1
_DYNAMIC_PASSWD_MAXLEN = 128

import urllib2, urllib, sys, hashlib, threading, json, time

from orzoj import conf, log, structures, control

_static_passwd = None
_passwd = None
_retry_cnt = None
_retry_wait = None
_timeout = None
_web_addr = None
_sched_interval = None
_thread_req_id = dict()

class _internal_error(Exception):
    def __init__(self, msg):
        self.msg = msg
    def __repr__(self):
        return self.msg

class Error(Exception):
    pass

def thread_sched_work():
    global _web_addr, _timeout, _sched_interval
    while not control.test_termination_flag():
        err = None
        try:
            ret = urllib2.urlopen(_web_addr + "?sched_work", None, _timeout).read()
            if ret != "0":
                err = ret
        except Exception as e:
            err = repr(e)
        if err is not None:
            log.error("error while refreshing website scheduled jobs: {0}" . format(err))
        time.sleep(_sched_interval)

def report_error(task, msg):
    """send a human-readable error message

    data: action=report_error, task=...(id:int), msg=...(:str)
    return: NULL

    Note:
        'data' is the data sent to website
        'return' is the data received from website"""
    _read({"action":"report_error", "task":task.id, "msg":msg})

def get_query_list():
    """return a list containing the queries for judge info

    data: action=get_query_list
    return: array of query list"""
    ret = _read({"action":"get_query_list"})
    if type(ret) != list:
        log.error("type check error")
        raise Error
    return ret

def register_new_judge(judge, query_ans):
    """register a new judge. @judge should be structures.judge,
    and query_ans should be a dict

    data: action=register_new_judge, judge=...(id:str), lang_supported=...,
        query_ans=json.dumps(query_ans)
    return: id_num=... (numeric judge id)"""
    try:
        judge.id_num = int(_read({"action":"register_new_judge", "judge":judge.id,
            "lang_supported":list(judge.lang_supported), "query_ans":json.dumps(query_ans)})["id_num"])
    except Exception as e:
        log.error("failed to register new judge: {0!r}" . format(e))
        raise Error

def remove_judge(judge):
    """
    data: action=remove_judge, judge=...(id:int)
    return: NULL"""
    _read({"action":"remove_judge", "judge":judge.id_num})

def fetch_task():
    """try to fetch a new task. return None if no new task available.
    this function does not raise exceptions

    data: action=fetch_task
    return: array("type"=>type, <type specified arguments>)
        type:
            "none" -- no new task
                      args: none
            "src"  -- new source file to be judged
                      args: id, prob, lang, src, input, output (see structures.py)"""
    try:
        ret = _read({"action":"fetch_task"})
        t = ret["type"]
        if t == "none":
            return
        if t == "src":
            v = structures.task()
            for i in v.__dict__:
                v.__dict__[i] = ret[i]
            v.id = int(v.id)
            return v
        raise _internal_error("unknown task type: {0!r}" . format(t))
    except Exception as e:
        log.error("failed to fetch task: {0!r}" . format(e))
        raise Error

def report_no_data(task):
    """tell the website that there are no data for the task
    this function does not raise exceptions
    
    data: action=report_no_data, task=...(id:int)
    return: NULL"""
    _read({"action":"report_no_data", "task":task.id})

def report_judge_waiting(task):
    """judge is waiting because it's serving another orzoj-server

    data: action=report_judge_waiting, task=...(id:int)
    return: NULL"""
    _read({"action":"report_judge_waiting", "task":task.id})

def report_compiling(task, judge):
    """now compiling @task on @judge

    data: action=report_compiling, task=...(id:int), judge=...(id:int)
    return: NULL"""
    _read({"action":"report_compiling", "task":task.id, "judge":judge.id_num})

def report_compile_success(task, ncase):
    """successfully compiled

    data: action=report_compile_success, task=...(id:int), ncase=...
    return: NULL"""
    _read({"action": "report_compile_success", "task": task.id, "ncase": ncase})

def report_compile_failure(task, info):
    """failed to compile

    data: action=report_compile_failure, task=...(id:int), info=...
    return: NULL"""
    _read({"action":"report_compile_failure", "task":task.id, "info":info})

def report_judge_progress(task, now):
    """
    @now: current case number, starting from 0

    data: action=report_judge_progress, task=...(id:int), now=...
    return: NULL"""
    _read({"action":"report_judge_progress", "task":task.id, "now": now})

def report_prob_result(task, result):
    """
    @result: list of case_result

    data: action=report_prob_result, task=...(id:int),
        exe_status=array(...), score=array(...), ... (see case_result in structures.py)
    return: NULL
    """
    data = {"action":"report_prob_result", "task":task.id}
    d = structures.case_result().__dict__
    for i in d:
        data[i] = [case.__dict__[i] for case in result]
    _read(data)


def _sha1sum(s):
    return hashlib.sha1(s).hexdigest()

def _read(data, maxlen = None):
    """if @maxlen is not None, data should be dict and is sent via GET method and without checksum
    and return the data read;
    otherwise @data is dumped by json and sent via POST method and return the data read

    Note: @maxlen is not None iff now trying to login
    """
    global _retry_cnt, _web_addr, _thread_req_id, _passwd

    def make_data():
        """return a tuple (checksum_base, data_sent)"""
        thread_id = threading.current_thread().ident
        try:
            req_id = _thread_req_id[thread_id]
        except KeyError:
            req_id = 0
        _thread_req_id[thread_id] = req_id + 1
        checksum_base = str(thread_id) + str(req_id) + _passwd
        data_sent = urllib.urlencode({"data" :
                json.dumps({"thread_id" : thread_id, "data" : data,
                    "checksum" : _sha1sum(checksum_base + data)})})

        return (checksum_base, data_sent)

    if maxlen:
        url = _web_addr + "?" + urllib.urlencode(data)
    else:
        data = json.dumps(data)
        (checksum_base, data_sent) = make_data()

    cnt = _retry_cnt

    while cnt:
        cnt -= 1
        try:
            ret = None

            if maxlen:
                return urllib2.urlopen(url, None, _timeout).read(maxlen)

            ret = urllib2.urlopen(_web_addr, data_sent, _timeout).read()

            if ret == 'relogin':
                log.warning("website requests relogin")
                _login()
                cnt = _retry_cnt
                _thread_req_id = dict()
                (checksum_base, data_sent) = make_data()
                continue

            ret = json.loads(ret)

            ret_status = ret["status"]
            ret_data = ret["data"]

            if ret["checksum"] != _sha1sum(checksum_base + str(ret_status) + ret_data):
                raise _internal_error("website checksum error")

            if int(ret_status):
                raise _internal_error("website says an error happens there: {0}" . format(ret_data))

            return json.loads(ret_data)

        except Exception as e:
            log.debug("raw data from server: {0!r}" . format(ret))
            log.error("website communication error [left retries: {0}]: {1!r}" .
                    format(cnt, e))
            sys.stderr.write("orzoj-server: website communication error. See the log for details.\n")
            time.sleep(_retry_wait);
            if control.test_termination_flag():
                raise Error
            continue

    raise Error

_first_login = True
def _login():
    """
    1. read at most _DYNAMIC_PASSWD_MAXLEN bytes from orz.php?action=login1&version=_VERSION,
       _dynamic_passwd is the data read
       _dynamic_passwd = "0" means version check error
    2. from orz.php?action=login2&checksum=_sha1sum(_sha1sum(_dynamic_passwd + _static_passwd)),
       and verify that it should be _sha1sum(_sha1sum(_dynamic_passwd) + _static_passwd)
    3. if it's the first time to login (i.e. relogin), send "refetch" to fetch all tasks with
        status "waiting on orzoj-server"
       """

    global _static_passwd, _passwd, _first_login

    try:

        try:
            _dynamic_passwd = _read({"action" : "login1", "version" : _VERSION},  _DYNAMIC_PASSWD_MAXLEN)

            if _dynamic_passwd == '0':
                raise _internal_error("website version check error")

            vpwd = _sha1sum(_sha1sum(_dynamic_passwd) + _static_passwd)
            _passwd = _sha1sum(_dynamic_passwd + _static_passwd)

            data = {"action" : "login2", "checksum" : _sha1sum(_passwd)}
            if _first_login:
                _first_login = False
                data["refetch"] = 1

            pwd_peer = _read(data, len(vpwd));

            if pwd_peer != vpwd:
                raise _internal_error("website verification error [peer returned: {0!r}]" .
                        format(pwd_peer))

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

def _set_web_addr(arg):
    global _web_addr
    _web_addr = arg[1].rstrip('/') + "/orz.php"

def _set_web_retry_cnt(arg):
    global _retry_cnt
    _retry_cnt = int(arg[1])
    if _retry_cnt == 0:
        _retry_cnt = 1

def _set_web_retry_wait(arg):
    global _retry_wait
    _retry_wait = float(arg[1])
    if _retry_wait < 1:
        _retry_wait = 1

def _set_web_sched_interval(arg):
    global _sched_interval
    _sched_interval = float(arg[1])
    if _sched_interval < 0.5:
        _sched_interval = 0.5

conf.simple_conf_handler("Password", _set_static_password)
conf.simple_conf_handler("WebTimeout", _set_web_timeout, "5")
conf.simple_conf_handler("WebAddress", _set_web_addr)
conf.simple_conf_handler("WebRetryCount", _set_web_retry_cnt, "5")
conf.simple_conf_handler("WebRetryWait", _set_web_retry_wait, "2")
conf.simple_conf_handler("WebSchedInterval", _set_web_sched_interval, "1")

conf.register_init_func(_login)

