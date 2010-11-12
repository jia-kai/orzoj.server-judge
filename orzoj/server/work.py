# $File: work.py
# $Author: Jiakai <jia.kai66@gmail.com>
# $Date: Wed Nov 10 15:09:01 2010 +0800
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

"""threads for waiting for tasks and managing judges"""

import threading, time, os, os.path, traceback
from collections import deque

from orzoj import log, snc, msg, structures, control, conf, sync_dir
from orzoj.server import web

_max_queue_size = None

_lang_id_dict = dict()
_lang_id_dict_lock = threading.Lock()

_judge_id_set = set()
_judge_id_set_lock = threading.Lock()

_refresh_interval = None
_id_max_len = None

class _internal_error(Exception):
    pass

def _get_lang_id(lang):
    global _lang_id_dict, _lang_id_dict_lock
    with _lang_id_dict_lock:
        return _lang_id_dict.setdefault(lang, len(_lang_id_dict))

class _Task_queue:
    def __init__(self):
        self._queue = dict()
        # dict of <language id:int> => <task queue:deque>
        self._lock = threading.Lock()
        self._size = 0

    def put(self, task):
        while self._is_full() and not control.test_termination_flag():
            time.sleep(msg.TELL_ONLINE_INTERVAL)
        with self._lock:
            if task.lang_id not in self._queue:
                self._queue[task.lang_id] = deque()
            self._queue[task.lang_id].append(task)
            self._size += 1

    def get(self, lang_id_set):
        """ return None if no usable"""
        ret = None
        with self._lock:
            min_tid = None
            for lid in lang_id_set:
                try:
                    q = self._queue[lid]
                    task = q[0]
                    if min_tid is None or task.id < min_tid:
                        min_tid = task.id
                        min_tid_q = q
                except Exception: # KeyError or IndexError
                    pass
            if min_tid is not None:
                ret = min_tid_q.popleft()
                self._size -= 1
        return ret

    def _is_full(self):
        global _max_queue_size
        with self._lock:
            return self._size >= _max_queue_size

_task_queue = _Task_queue()

class _thread_web_communicate(threading.Thread):

    class _callable:
        def __init__(self, func, args, par):
            self._func = func
            self._args = args
            self._par = par

        def call(self):
            if self._func is not None:
                try:
                    self._func(*self._args)
                except web.Error:
                    self._par._on_error.set()
                except Exception as e:
                    log.error("error while communicating with orzoj-website: {0}" . format(e))
                    self._par._on_error.set()
                self._func = None


    def __init__(self):
        threading.Thread.__init__(self)
        self._is_stopped = False
        self._on_error = threading.Event()
        self._cd = threading.Condition()

        self._queue = deque()
        self._lazy = None

    def lazy_report(self, func, args):
        self._cd.acquire()
        self._lazy = _thread_web_communicate._callable(func, args, self)
        self._cd.notify()
        self._cd.release()

    def report(self, func, args):
        self._cd.acquire()
        self._queue.append(_thread_web_communicate._callable(func, args, self))
        self._cd.notify()
        self._cd.release()

    def clean_lazy(self):
        self._cd.acquire()
        self._lazy = None
        self._cd.notify()
        self._cd.release()

    def check_error(self):
        return self._on_error.is_set()

    def stop(self):
        self._cd.acquire()
        self._is_stopped = True
        self._cd.notify()
        self._cd.release()

    def run(self):
        while True:
            self._cd.acquire()
            if self._is_stopped and len(self._queue) == 0:
                return

            if len(self._queue):
                cur_task = self._queue.popleft()
            elif (self._lazy):
                cur_task = self._lazy
                self._lazy = None
            else:
                cur_task = None

            if cur_task is None:
                self._cd.wait()
                self._cd.release()
            else:
                self._cd.release()
                cur_task.call()


def thread_work():
    """wait for tasks and distribute them to judges"""
    global _task_queue, _refresh_interval

    threading.Thread(target = web.thread_sched_work, name = "web.thread_web_sched_work").start()

    while not control.test_termination_flag():
        while not control.test_termination_flag():
            try:
                task = web.fetch_task()
            except web.Error as e:
                log.error("ending program because of communication error with website")
                control.set_termination_flag()
                return
            if task is None:
                break

            task.lang_id = _get_lang_id(task.lang)
            _task_queue.put(task)

            log.info("fetched task #{0} from website" . format(task.id))

        time.sleep(_refresh_interval)


class thread_new_judge_connection(threading.Thread):
    def __init__(self, sock):
        """serve a new connection, which should be orzoj-judge.
        No exceptions are raised, exit silently on error
        sock will be closed"""
        threading.Thread.__init__(self, name = "work.thread_new_judge_connection")
        self._sock = sock
        self._snc = None
        self._cur_task = None
        self._web_registered = False
        self._judge = structures.judge()
        self._lang_id_set = set()

    def _clean(self):
        global _task_queue, _judge_id_set, _judge_id_set_lock

        if self._cur_task:
            _task_queue.put(self._cur_task)
            self._cur_task = None

        judge = self._judge
        if judge.id:
            with _judge_id_set_lock:
                _judge_id_set.remove(judge.id)

        if self._web_registered:
            try:
                web.remove_judge(judge)
            except web.Error:
                log.warning("[judge {0!r}] failed to unregister on website" . format(judge.id))

        log.info("[judge {0!r}] disconnected" . format(judge.id))

    def run(self):
        judge = self._judge
        def _write_msg(m):
            msg.write_msg(self._snc, m)

        def _write_str(s):
            self._snc.write_str(s)

        def _read_msg():
            return msg.read_msg(self._snc)

        def _read_str():
            return self._snc.read_str()

        def _read_uint32():
            return self._snc.read_uint32()

        def _check_msg(m):
            if m != _read_msg():
                log.warning("[judge {0!r}] message check error" .
                        format(judge.id))
                raise _internal_error

        global _id_max_len, _judge_id_set, _judge_id_set_lock

        try:
            self._snc = snc.snc(self._sock, True)
            _check_msg(msg.HELLO)
            judge_id = _read_str()

            if len(judge_id) > _id_max_len:
                _write_msg(msg.ID_TOO_LONG)
                raise _internal_error

            with _judge_id_set_lock:
                if judge_id in _judge_id_set:
                    _write_msg(msg.DUPLICATED_ID)
                    log.warning("another judge declares duplicated id {0!r}" .
                            format(judge_id))
                    raise _internal_error

                _judge_id_set.add(judge_id)

            judge.id = judge_id
            del judge_id

            if _read_uint32() != msg.PROTOCOL_VERSION:
                log.warning("[judge {0!r}] version check error" .
                        format(judge.id))
                _write_msg(msg.ERROR)
                raise _internal_error

            cnt = _read_uint32()
            while cnt:
                cnt -= 1
                lang = _read_str()
                judge.lang_supported.add(lang)
                self._lang_id_set.add(_get_lang_id(lang))

            _write_msg(msg.CONNECT_OK)

            query_ans = dict()
            for i in web.get_query_list():
                _write_msg(msg.QUERY_INFO)
                _write_str(i)
                _check_msg(msg.ANS_QUERY)
                query_ans[i] = _read_str()

            web.register_new_judge(judge, query_ans)
            self._web_registered = True

            log.info("[judge {0!r}] successfully connected" . format(judge.id))

            while not control.test_termination_flag():
                self._solve_task()

            self._snc.close()
            self._sock.close()

        except snc.Error:
            log.warning("[judge {0!r}] failed because of network error" . format(judge.id))
            self._clean()
        except _internal_error:
            self._clean()
        except web.Error:
            log.warning("[judge {0!r}] failed because of error while communicating with website" . format(judge.id))
            _write_msg(msg.ERROR)
            self._clean()
        except sync_dir.Error:
            log.warning("[judge {0!r}] failed to synchronize data directory" .
                    format(judge.id))
            self._clean()
        except Exception as e:
            log.warning("[judge {0!r}] error happens: {1}" .
                    format(judge.id, e))
            log.debug(traceback.format_exc())
            self._clean()

    def __del__(self):
        if self._snc:
            self._snc.close()
        self._sock.close()

    def _solve_task(self):
        judge = self._judge
        def _write_msg(m):
            msg.write_msg(self._snc, m)

        def _write_str(s):
            self._snc.write_str(s)

        def _write_uint32(v):
            self._snc.write_uint32(v)

        def _read_msg():
            return msg.read_msg(self._snc)

        def _read_str():
            return self._snc.read_str()

        def _read_uint32():
            return self._snc.read_uint32()

        def _check_msg(m):
            if m != _read_msg():
                log.warning("[judge {0!r} message check error" .
                        format(judge.id))
                raise _internal_error
            
        def _stop_web_report(tell_online = True):
            th_report.stop()
            if tell_online:
                while th_report.is_alive():
                    th_report.join(msg.TELL_ONLINE_INTERVAL)
                    _write_msg(msg.TELL_ONLINE)
            else:
                th_report.join()

        global _task_queue
        task = _task_queue.get(self._lang_id_set)
        if task is None:
            _write_msg(msg.TELL_ONLINE)
            time.sleep(msg.TELL_ONLINE_INTERVAL)
            return
        
        log.info("[judge {0!r}] received task #{1} for problem {2!r}" .
                format(judge.id, task.id, task.prob))

        self._cur_task = task

        th_report = _thread_web_communicate()
        th_report.start()

        if not os.path.isdir(task.prob):
            self._cur_task = None
            log.error("No data for problem {0!r}, task #{1} discarded" .
                    format(task.prob, task.id))
            th_report.report(web.report_no_data, [task])
            _stop_web_report()
            return

        th_report.report(web.report_sync_data, [task, judge])
        _write_msg(msg.PREPARE_DATA)
        _write_str(task.prob)
        
        speed = sync_dir.send(task.prob, self._snc)
        if speed:
            log.info("[judge {0!r}] file transfer speed: {1!r} kb/s" . 
                    format(judge.id, speed))

        m = _read_msg()

        if m == msg.DATA_ERROR:
            self._cur_task = None
            reason = _read_str()
            log.error("[judge {0!r}] [task #{1}] [prob: {2!r}] data error:\n{3}" . 
                    format(judge.id, task.id, task.prob, reason))
            th_report.report(web.report_error, [task, "data error"])
            _stop_web_report()
            return
        elif m != msg.DATA_OK:
            log.warning("[judge {0!r}] message check error" . format(judge.id))
            th_report.report(web.report_error, [task, "message check error"])
            _stop_web_report(False)
            raise _internal_error

        ncase = _read_uint32()

        _write_msg(msg.START_JUDGE)
        _write_str(task.lang)
        _write_str(task.src)
        _write_str(task.input)
        _write_str(task.output)

        while True:
            m = _read_msg()
            if m == msg.START_JUDGE_OK:
                break
            if m != msg.START_JUDGE_WAIT:
                log.warning("[judge {0!r}] message check error" .
                        format(judge.id))
                th_report.report(web.report_error, [task, "message check error"])
                _stop_web_report(False)
                raise _internal_error

        th_report.report(web.report_compiling, [task])

        while True:
            m = _read_msg()
            if m == msg.TELL_ONLINE:
                continue

            if m == msg.COMPILE_SUCCEED:
                th_report.report(web.report_compile_success, [task, ncase])
                break
            else:
                if m != msg.COMPILE_FAIL:
                    th_report.report(web.report_error, [task, "message check error"])
                    log.warning("[judge {0!r}] message check error" .
                            format(judge.id))
                    _stop_web_report(False)
                    raise _internal_error
                self._cur_task = None
                th_report.report(web.report_compile_failure, [task, _read_str()])
                _stop_web_report()
                return

        prob_res = list()

        for i in range(ncase):
            th_report.lazy_report(web.report_judge_progress, [task, i])
            while True:
                m = _read_msg()
                if m == msg.REPORT_CASE:
                    break
                if m != msg.TELL_ONLINE:
                    log.warning("[judge {0!r}] message check error" .
                            format(judge.id))
                    th_report.report(web.report_error, [task, "message check error"])
                    _stop_web_report(False)
                    raise _internal_error
            result = structures.case_result()
            result.read(self._snc)
            prob_res.append(result)

        th_report.clean_lazy()
        th_report.report(web.report_prob_result, [task, prob_res])

        _check_msg(msg.REPORT_JUDGE_FINISH)

        self._cur_task = None
        _stop_web_report()

        if th_report.check_error():
            log.warning("[judge {0!r}] error while reporting judge results for task #{1}" .
                    format(judge.id, task.id))
        else:
            log.info("[judge {0!r}] finished task #{1} normally" .
                    format(judge.id, task.id))



def _set_refresh_interval(arg):
    global _refresh_interval
    _refresh_interval = float(arg[1])
    if _refresh_interval < 1:
        raise conf.UserError("Option {0} can not be less than 1 second" . format(arg[0]))

def _set_id_max_len(arg):
    global _id_max_len
    _id_max_len = int(arg[1])
    if _id_max_len < 1:
        raise conf.UserError("Option {0} can not be less than 1" . format(arg[0]))

def _set_data_dir(arg):
    os.chdir(arg[1])

def _set_max_queue_size(arg):
    global _max_queue_size
    _max_queue_size = int(arg[1])

conf.simple_conf_handler("RefreshInterval", _set_refresh_interval, default = "2")
conf.simple_conf_handler("JudgeIdMaxLen", _set_id_max_len, default = "20")
conf.simple_conf_handler("DataDir", _set_data_dir)
conf.simple_conf_handler("MaxQueueSize", _set_max_queue_size, default = "1024")

