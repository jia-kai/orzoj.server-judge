# $File: work.py
# $Author: Jiakai <jia.kai66@gmail.com>
# $Date: Fri Oct 29 10:49:02 2010 +0800
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

import threading, Queue, time, os, os.path, hashlib
from orzoj import log, snc, msg, structures, control, conf, filetrans
from orzoj.server import web

_judge_online = {}
_lock_judge_online = threading.Lock()

_task_queue = None
_max_queue_size = None

_refresh_interval = None
_id_max_len = None

_QUEUE_TIMEOUT = 0.5
_CASE_CHECK_ADDITION_TIMEOUT = 10

class _internal_error(Exception):
    pass

def _add_task(task):
    while not control.test_termination_flag():
        try:
            _task_queue.put(task, True, _QUEUE_TIMEOUT)
            break
        except Queue.Full:
            continue

def _thread_fetch_task():
    global _judge_online, _lock_judge_online, _refresh_interval, _id_max_len
    global _QUEUE_TIMEOUT

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

            _add_task(task)

            log.debug("fetched task #{0}" . format(task.id))

        time.sleep(_refresh_interval)

class _thread_report_judge_progress(threading.Thread):
    def __init__(self, task):
        threading.Thread.__init__(self)
        self._task = task
        self._now = 0
        self._stop = threading.Event()
        self._lock = threading.Lock()

    def run(self):
        while not self._stop.is_set():
            with self._lock:
                n = self._now
            try:
                web.report_judge_progress(self._task, n)
            except web.Error:
                log.error("failed to report judge progress for task #{0}" . format(self._task.id))

    def stop(self):
        self._stop.set()

    def set_progress(self, now):
        with self._lock:
            self._now = now

def thread_work():
    """wait for tasks and distribute them to judges"""
    global _judge_online, _lock_judge_online, _task_queue, _refresh_interval, _id_max_len
    global _QUEUE_TIMEOUT

    threading.Thread(target = _thread_fetch_task, name = "work._thread_fetch_task").start()
    threading.Thread(target = web.thread_sched_work, name = "web.thread_web_sched_work").start()

    while not control.test_termination_flag():
        try:
            task = _task_queue.get(True, _QUEUE_TIMEOUT)
            judge = None

            with _lock_judge_online:
                for (i, j) in _judge_online.iteritems():
                    if task.lang in j.lang_supported:
                        if judge is None or j.queue.qsize() < judge.queue.qsize():
                            judge = j

            if judge is None:
                _add_task(task)
                time.sleep(0.5)
                if "no_judge_reported" not in task.__dict__:
                    log.warning("no judge for task #{0} (lang: {1!r})" . format(task.id, task.lang))
                    task.no_judge_reported = True
            else:
                log.info('distribute task #{0} to judge {1!r}' .
                        format(task.id, judge.id))
                while not control.test_termination_flag():
                    try:
                        with _lock_judge_online: # the chosen judge may have just deleted itself, so we have to lock
                            if judge.id in _judge_online:
                                judge.queue.put(task, True, _QUEUE_TIMEOUT)
                            else:
                                _add_task(task)
                                break
                    except Queue.Full:
                        log.warning('task queue for judge {0!r} is full, retrying...' . 
                                format(judge.id))
                        continue
                    break

        except Queue.Empty:
            pass

def _get_file_list(path):
    """return a dict containing regular files and their corresponding sha1 digests in the direcory @path.
    return None on error"""
    def _sha1_file(path):
        with open(path, 'rb') as f:
            sha1_ctx = hashlib.sha1()
            while True:
                buf = f.read(sha1_ctx.block_size)
                if not buf:
                    return sha1_ctx.digest()
                sha1_ctx.update(buf)

    try:
        ret = {}
        for i in os.listdir(path):
            pf = os.path.normpath(os.path.join(path, i))
            if os.path.isfile(pf):
                ret[i] = _sha1_file(pf)
        return ret
            
    except OSError as e:
        log.error("failed to obtain file list of {0!r}: [errno {1}] [filename {2!r}]: {3}" .
                format(path, e.errno, e.filename, e.strerror))
        return None
    except Exception as e:
        log.error("failed to obtain file list of {0!r}: {1!r}" .
                format(path, e))
        return None

class thread_new_judge_connection(threading.Thread):
    def __init__(self, sock):
        """serve a new connection, which should be orzoj-judge.
        No exceptions are raised, exit silently on error."""
        threading.Thread.__init__(self, name = "work.thread_new_judge_connection")
        self._sock = sock

    def _clean(self):
        global _judge_online, _lock_judge_online

        if self._cur_task != None:
            _add_task(self._cur_task)
            self._cur_task = None

        judge = self._judge
        if judge.id is not None:
            with _lock_judge_online:
                if judge.id in _judge_online:
                    del _judge_online[judge.id]
            log.info("[judge {0!r}] disconnected" . format(judge.id))

        if self._web_registered:
            try:
                web.remove_judge(judge)
            except web.Error:
                pass

        if judge.queue:
            try:
                while not control.test_termination_flag():
                    task = judge.queue.get_nowait()
                    log.info("[judge {0!r}] sending task #{1} back to main task queue" .
                            format(judge.id, task.id))
                    _add_task(task)
            except Queue.Empty:
                return


    def _solve_task(self):
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
                        format(self._id))
                raise _internal_error

        judge = self._judge
        try:
            task = judge.queue.get(True, _QUEUE_TIMEOUT)
        except Queue.Empty:
            _write_msg(msg.TELL_ONLINE)
            return
        
        log.info("[judge {0!r}] received task #{1} for problem {2!r}" .
                format(self._id, task.id, task.prob))

        self._cur_task = task

        datalist = _get_file_list(task.prob)
        if datalist is None:
            self._cur_task = None
            log.error("No data for problem {0!r}, task discarded" .
                    format(task.prob))
            web.report_no_data(task)
            return

        web.report_sync_data(task, judge)
        _write_msg(msg.PREPARE_DATA)
        _write_str(task.prob)
        _write_uint32(len(datalist))

        for (f, sha1) in datalist.iteritems():
            _write_str(f)
            _write_str(sha1)

        while True:
            m = _read_msg()
            if m == msg.DATA_OK:
                break

            if m == msg.DATA_COMPUTING_SHA1:
                continue

            if m == msg.DATA_ERROR:
                self._cur_task = None
                reason = _read_str()
                log.error("[judge {0!r}] data error [prob: {1!r}]: {2!r}" . 
                        format(self._id, task.prob, reason))
                web.report_error(task, "data error: {0!r}" . format(reason))
                return

            if m != msg.NEED_FILE:
                log.warning("[judge {0!r}] message check error" . format(self._id))
                web.report_error(task, "message check error")
                raise _internal_error

            fpath = os.path.normpath(os.path.join(task.prob, _read_str()))
            speed = filetrans.send(fpath, self._snc)
            log.info("[judge {0!r}] file transfer speed: {1} kb/s" .
                    format(self._id, speed))

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
                        format(self._id))
                web.report_error(task, "message check error")
                raise _internal_error

        web.report_compiling(task)

        while True:
            m = _read_msg()
            if m == msg.TELL_ONLINE:
                continue

            if m == msg.COMPILE_SUCCEED:
                web.report_compile_success(task, ncase)
                break
            else:
                if m != msg.COMPILE_FAIL:
                    web.report_error(task, "message check error")
                    log.warning("[judge {0!r}] message check error" .
                            format(self._id))
                    raise _internal_error
                web.report_compile_failure(task, _read_str())
                self._cur_task = None
                return

        th_progress = _thread_report_judge_progress(task)
        th_progress.start()
        prob_res = list()

        for i in range(ncase):
            th_progress.set_progress(i)
            while True:
                m = _read_msg()
                if m == msg.REPORT_CASE:
                    break
                if m != msg.TELL_ONLINE:
                    th_progress.stop()
                    th_progress.join()
                    web.report_error(task, "message check error")
                    log.warning("[judge {0!r}] message check error" .
                            format(self._id))
                    raise _internal_error
            result = structures.case_result()
            result.read(self._snc)
            prob_res.append(result)

        th_progress.stop()
        _check_msg(msg.REPORT_JUDGE_FINISH)
        th_progress.join()

        web.report_prob_result(task, prob_res)

        self._cur_task = None

        log.info("[judge {0!r}] finished task #{1} normally" .
                format(self._id, task.id))


    def run(self):
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
                        format(self._id))
                raise _internal_error

        global _judge_online, _lock_judge_online, _refresh_interval, _id_max_len
        global _QUEUE_TIMEOUT

        self._cur_task = None
        self._web_registered = False
        self._id = "None"

        judge = structures.judge()
        judge.queue = None
        self._judge = judge
        try:
            self._snc = snc.snc(self._sock, True)
            _check_msg(msg.HELLO)
            judge.id = _read_str()
            self._id = judge.id

            if len(judge.id) > _id_max_len:
                _write_msg(msg.ID_TOO_LONG)
                raise _internal_error

            with _lock_judge_online:
                if judge.id in _judge_online:
                    _write_msg(msg.DUPLICATED_ID)
                    log.warning("another judge declares duplicated id {0!r}" .
                            format(judge.id))
                    raise _internal_error

            if _read_uint32() != msg.PROTOCOL_VERSION:
                log.warning("[judge {0!r}] version check error" .
                        format(self._id))
                _write_msg(msg.ERROR)
                raise _internal_error

            cnt = _read_uint32()
            while cnt:
                cnt -= 1
                judge.lang_supported.add(_read_str())

            _write_msg(msg.CONNECT_OK)

            query_ans = {}
            for i in web.get_query_list():
                _write_msg(msg.QUERY_INFO)
                _write_str(i)
                _check_msg(msg.ANS_QUERY)
                query_ans[i] = _read_str()

            web.register_new_judge(judge, query_ans)
            self._web_registered = True

            global _max_queue_size
            judge.queue = Queue.Queue(_max_queue_size)

            with _lock_judge_online:
                _judge_online[judge.id] = judge

            log.info("[judge {0!r}] successfully connected" . format(judge.id))

            while not control.test_termination_flag():
                self._solve_task()

            self._snc.close()
            self._sock.close()

        except snc.Error:
            log.warning("[judge {0!r}] failed because of network error" . format(self._id))
            self._clean()
            return
        except _internal_error:
            self._snc.close()
            self._sock.close()
            self._clean()
            return
        except web.Error:
            log.warning("[judge {0!r}] failed because of error while communicating with website" . format(self._id))
            _write_msg(msg.ERROR)
            self._snc.close()
            self._sock.close()
            self._clean()
            return
        except filetrans.OFTPError:
            log.warning("[judge {0!r}] failed to transfer file" .
                    format(self._id))
            self._snc.close()
            self._sock.close()
            self._clean()
            return

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

def _init_queue():
    global _task_queue, _max_queue_size
    _task_queue = Queue.Queue(_max_queue_size)

conf.simple_conf_handler("RefreshInterval", _set_refresh_interval, default = "2")
conf.simple_conf_handler("JudgeIdMaxLen", _set_id_max_len, default = "20")
conf.simple_conf_handler("DataDir", _set_data_dir)
conf.simple_conf_handler("MaxQueueSize", _set_max_queue_size, default = "1024")

conf.register_init_func(_init_queue)

