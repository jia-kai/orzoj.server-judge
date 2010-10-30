# $File: core.py
# $Author: Jiakai <jia.kai66@gmail.com>
# $Date: Sat Oct 30 14:17:56 2010 +0800
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
"""core of orzoj-judge, which compiles (by running the compiler)
and executes (by running the executor under limiter) user's
program and verifies the output"""

import os.path, errno, shutil, time, os, shlex, threading, Queue, stat

try:
    import fcntl
except:
    pass

class Error(Exception):
    pass

from orzoj import conf, log, structures, msg, snc
from orzoj.judge import limiter

_DEFAULT_PROG_NAME = "prog"  # file name of program being judged (without extention)

_dir_temp = None  # relative to ChrootDir
_dir_temp_abs = None

_prog_path = None  # path of program being judged, without extention (relative to ChrootDir)
_prog_path_abs = None

_lock_file_obj = None
_lock_file_fd = None

_executor_dict = dict()
lang_dict = dict()

_cmd_vars = dict()

def _join_path(p1, p2):
    return os.path.normpath(os.path.join(p1, p2))

def _eval(s, prog):
    """evaluate argument passed to AddExecutor"""
    global _cmd_vars
    if s[0] != '$':
        return s.replace("%s", prog)
    try:
        return eval(s[1:], {}, _cmd_vars)
    except Exception as e:
        log.error("[executor {0!r}] error while evaluating argument {1!r}: {2!r}" .
                format(self._name, s, e))
        raise

def _clean_temp():
    """clean temporary directory"""
    global _dir_temp_abs
    try:
        for i in os.listdir(_dir_temp_abs):
            p = _join_path(_dir_temp_abs, i)
            if os.path.isdir(p) and not os.path.islink(p):
                shutil.rmtree(p)
            else:
                os.remove(p)
    except Exception as e:
        log.error("failed to clean temporary directory [{0!r}]: {1!r}" .
                format(_dir_temp_abs, e))
        raise Error

class _thread_report_case_result(threading.Thread):
    def __init__(self, conn, ncase):
        threading.Thread.__init__(self)
        self._conn = conn
        self._ncase = ncase
        self._queue = Queue.Queue()
        self._error = None

    def run(self):
        try:
            while self._ncase:
                try:
                    res = self._queue.get(False)
                    msg.write_msg(self._conn, msg.REPORT_CASE)
                    res.write(self._conn)
                    self._ncase -= 1
                except Queue.Empty:
                    msg.write_msg(self._conn, msg.TELL_ONLINE)
                    time.sleep(0.5)
        except Exception as e:
            log.error("failed to report case result: {0!r}" . format(e))
            self._error = e

    def check_error(self):
        if self._error is not None:
            raise self._error

    def add(self, res):
        self._queue.put(res)


class _thread_tell_online(threading.Thread):
    def __init__(self, conn):
        threading.Thread.__init__(self)
        self._conn = conn
        self._stop = threading.Event()

    def run(self):
        while not self._stop.is_set():
            msg.write_msg(self._conn, msg.TELL_ONLINE)
            time.sleep(0.5)

    def stop(self):
        self._stop.set()


class _Executor:
    def __init__(self, args):
        if len(args) < 4:
            raise conf.UserError("Option {0} takes at least three arguments" . format(args[0]))

        global _executor_dict
        if args[1] in _executor_dict:
            raise conf.UserError("duplicated executor name: {0!r}" . foramt(args[1]))

        if args[2] not in limiter.limiter_dict:
            raise conf.UserError("unknown limiter {0!r} for executor {1!r}" . 
                    format(args[2], args[1]))

        _executor_dict[args[1]] = self
        self._name = args[1]
        self._limiter = limiter.limiter_dict[args[2]]
        self._args = args[3:]

    def run_as_compiler(self, fsrc, extra_args = None):
        """run the executor as compiler (retrieve stderr) and substitute "%s" for @fsrc,
        return a tuple (success, info),
        where success is a boolean value indicating whether it's compiled successfully,
        while info is the executor output or a string indicating some system error (human readable)
        if successfully compiled, info is None

        @extra_args can be a list of string
            
        no exceptions are raised"""

        global _cmd_vars

        try:
            try:
                if extra_args is None:
                    args = [_eval(i, fsrc) for i in self._args]
                else:
                    args = [_eval(i, fsrc) for i in self._args + extra_args]
            except Exception:
                return (False, "failed to compile: executor configuration error")

            l = self._limiter
            _cmd_vars["TARGET"] = args

            l.run(_cmd_vars, stdout = limiter.SAVE_OUTPUT, stderr = limiter.SAVE_OUTPUT)

            if l.exe_status:
                if l.exe_status == structures.EXESTS_EXIT_NONZERO:
                    return (False, l.stdout + l.stderr)
                else:
                    return (False, "failed to compile: {0}: details: {1}" .
                            format(structures.EXECUTION_STATUS_STR[l.exe_status],
                                l.exe_extra_info))
            return (True, None)
        except limiter.SysError as e:
            return (False, "failed to compile: limiter error: {0} [stderr: {1!r}]" .
                    format(e.msg, l.stderr))
        except Exception as e:
            return (False, "failed to compile: caught exception: {0!r}" .
                    format(e))

    def run(self, prog, stdin = None, stdout = None, retrieve_stdout = False, extra_args = None):
        """execute user's program @prog, stdin and stdout can be redirected to file
        allowed @stdin and @stdout values are the same as that of subprocess.Popen
        return an instance of structures.case_result

        if retrieve_stdout is True, return a tuple(res:structures.case_result, stdout:str),
        and @stdin and @stdout are ignored
        
        no exceptions are raised"""

        global _cmd_vars
        res = structures.case_result()

        def mkerror(msg):
            res.exe_status = structures.EXESTS_SYSTEM_ERROR
            res.score = 0
            res.full_score = 0
            res.time = 0
            res.memory = 0
            res.extra_info = msg
            if retrieve_stdout:
                res = (res, None)

        try:
            try:
                args = [_eval(i, prog) for i in self._args]
            except Exception:
                mkerror("failed to execute: executor configuration error")
                return res

            if extra_args:
                args.extend(extra_args)

            l = self._limiter
            _cmd_vars["TARGET"] = args

            if retrieve_stdout:
                l.run(_cmd_vars, stdout = limiter.SAVE_OUTPUT, stderr = limiter.get_null_dev())
            else:
                l.run(_cmd_vars, stdin = stdin, stdout = stdout, stderr = limiter.get_null_dev())

            res.score = 0
            res.full_score = 0
            res.exe_status = l.exe_status
            res.time = l.exe_time
            res.memory = l.exe_mem
            res.extra_info = l.exe_extra_info

            if retrieve_stdout:
                return (res, l.stdout)
            return res
        
        except limiter.SysError as e:
            mkerror("failed to execute: limiter error: {0}" .
                    format(e.msg))
            return res

        except Exception as e:
            mkerror("failed to execute: caught exception: {0!r}" .
                    format(e))
            return res

class _Lang:
    def __init__(self, args):
        if len(args) != 6:
            raise conf.UserError("Option {0} takes five arguments, but {1} is(are) given" .
                    format(args[0], len(args) - 1))

        global _executor_dict, lang_dict

        if args[1] in lang_dict:
            raise conf.UserError("duplicated language: {0!r}" . format(args[1]))

        self._name = args[1]
        self._src_ext = args[2]
        self._exe_ext = args[3]

        if args[4] == "None":
            self._compiler = None
        else:
            if args[4] not in _executor_dict:
                raise conf.UserError("unknown compiler executor {0!r} for language {1!r}" .
                        format(args[4], args[1]))
            self._compiler = _executor_dict[args[4]]

        if args[5] not in _executor_dict:
            raise conf.UserError("unknown program executor {0!r} for language {1!r}" .
                    format(args[5], args[1]))
        self._executor = _executor_dict[args[5]]

        lang_dict[args[1]] = self

    def judge(self, conn, pcode, pconf, src, input, output):
        """@pcode: problem code
        @pconf: problem configuration (defined in probconf.py)
        may raise Error or snc.Error"""

        def _write_msg(m):
            msg.write_msg(conn, m)

        def _write_str(s):
            conn.write_str(s)

        def _write_uint32(v):
            conn.write_uint32(v)

        locked = False

        global _lock_file_fd
        if _lock_file_fd:
            while True:
                try:
                    fcntl.flock(_lock_file_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except IOError as e:
                    if e.errno == errno.EACCES or e.errno == errno.EAGAIN:
                        _write_msg(msg.START_JUDGE_WAIT)
                        time.sleep(0.5)
                        continue
                    else:
                        log.error("failed to lock file: {0!r}" . format(e))
                        _write_msg(msg.ERROR)
                        raise Error

                except Exception as e:
                    log.error("failed to lock file: {0!r}" . format(e))
                    _write_msg(msg.ERROR)
                    raise Error

                locked = True
                break  # successfully locked 

        try:
            _write_msg(msg.START_JUDGE_OK)

            _clean_temp()

            global _prog_path_abs, _cmd_vars

            if self._compiler:
                with open(_prog_path_abs + self._src_ext, "w") as f:
                    f.write(src)

                _cmd_vars["MEMORY"] = 0
                _cmd_vars["DATADIR"] = os.path.abspath(pcode)

                th_tell_online = _thread_tell_online(conn)
                th_tell_online.start()

                if pconf.compiler and self._name in pconf.compiler:
                    (ok, info) = self._compiler.run_as_compiler(_prog_path_abs, pconf.compiler[self._name])
                else:
                    (ok, info) = self._compiler.run_as_compiler(_prog_path_abs)

                th_tell_online.stop()
                th_tell_online.join()

                if not ok:
                    _write_msg(msg.COMPILE_FAIL)
                    _write_str(info)
                    return

            _write_msg(msg.COMPILE_SUCCEED)

            global _dir_temp_abs

            if pconf.extra_input:
                for i in pconf.extra_input:
                    shutil.copy(_join_path(pcode, i), _dir_temp_abs)

            os.chmod(_prog_path_abs + self._exe_ext,
                    stat.S_IRUSR | stat.S_IXUSR |
                    stat.S_IRGRP | stat.S_IXGRP |
                    stat.S_IROTH | stat.S_IXOTH)
            global _prog_path
            prog_path = _prog_path + self._exe_ext

            th_report_case = _thread_report_case_result(conn, len(pconf.case))
            th_report_case.start()

            for case in pconf.case:

                try:
                    stdin_path = _join_path(pcode, case.stdin)
                    if not input: # use stdin
                        prog_fin = open(stdin_path)
                    else:
                        tpath = _join_path(_dir_temp_abs, input)
                        shutil.copy(stdin_path, tpath)
                        os.chmod(tpath, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
                        prog_fin = limiter.get_null_dev(False)

                    if not output: # use stdout
                        prog_fout_path = _join_path(_dir_temp_abs, "output.{0}" .
                                format(time.time()))
                        prog_fout = open(prog_fout_path, "w")
                    else:
                        prog_fout_path = _join_path(_dir_temp_abs, output)
                        prog_fout = limiter.get_null_dev()
                except Exception as e:
                    log.error("failed to open data file: {0!r}" . format(e))
                    case_result = structures.case_result()
                    case_result.exe_status = structures.EXESTS_SYSTEM_ERROR
                    case_result.score = 0
                    case_result.full_score = 0
                    case_result.time = 0
                    case_result.memory = 0
                    case_result.extra_info = "failed to open data file"

                else:

                    _cmd_vars["TIME"] = case.time
                    _cmd_vars["MEMORY"] = case.mem

                    umask_prev = os.umask(0)
                    case_result = self._executor.run(prog_path, stdin = prog_fin, stdout = prog_fout)
                    case_result.full_score = case.score
                    os.umask(umask_prev)

                    if prog_fin:
                        prog_fin.close()
                    if prog_fout:
                        prog_fout.close()

                    if case_result.exe_status == structures.EXESTS_NORMAL:
                        if (not os.path.isfile(prog_fout_path)) or os.path.islink(prog_fout_path):
                            (case_result.score, case_result.extra_info) = (0, "output file not found")
                        else:
                            (case_result.score, case_result.extra_info) = pconf.verify_func(case.score, stdin_path, 
                                _join_path(pcode, case.stdout), prog_fout_path)

                    if input:
                        try:
                            os.unlink(tpath)
                        except Exception as e:
                            log.error("failed to remove program input file: {0!r}" . format(e))
                    try:
                        os.unlink(prog_fout_path)
                    except Exception as e:
                        log.error("failed to remove program output file: {0!r}" . format(e))
                th_report_case.add(case_result)

            th_report_case.join()
            th_report_case.check_error()
            _write_msg(msg.REPORT_JUDGE_FINISH)

            if locked:
                fcntl.flock(_lock_file_fd, fcntl.LOCK_UN)

        except Error:
            if locked:
                fcntl.flock(_lock_file_fd, fcntl.LOCK_UN)
            raise
        except snc.Error:
            if locked:
                fcntl.flock(_lock_file_fd, fcntl.LOCK_UN)
            raise Error
        except Exception as e:
            if locked:
                fcntl.flock(_lock_file_fd, fcntl.LOCK_UN)
            log.error("[lang {0!r}] failed to judge: {1!r}" .
                    format(self._name, e))
            _write_msg(msg.ERROR)
            raise Error

    def verifier_compile(self, pcode, fsrc, src, extra_args = None):
        """return a tuple(success, info, exe_path), for success and info, refer to _Executor::run_as_compiler
        @fsrc is the expected file path (no extention)
        @src is the source (string)

        @extra_args can be a string and will be splited

        may raise Error if failed to write source file"""
        if not self._compiler:
            try:
                fsrc = fsrc + self._exe_ext
                with open(fsrc, "w") as f:
                    f.write(src)
                return (True, None, fsrc)
            except Exception as e:
                log.error("failed to write source to {0!r}: {1!f}" .
                        format(fsrc, e))
                raise Error

        srcpath = fsrc + self._src_ext
        try:
            with open(srcpath, "w") as f:
                f.write(src)
        except Exception as e:
            log.error("failed to write source to {0!r}: {1!f}" .
                    format(srcpath, e))
            raise Error

        _cmd_vars["MEMORY"] = 0
        _cmd_vars["DATADIR"] = os.path.abspath(pcode)

        if extra_args:
            extra_args = shlex.split(extra_args)
        ret = self._compiler.run_as_compiler(fsrc, extra_args)

        ret = (ret[0], ret[1], fsrc + self._exe_ext)

        try:
            os.remove(srcpath)
            return ret
        except Exception as e:
            log.error("failed to remove file {0!r}: {1!f}" .
                    format(srcpath, e))
            raise Error


    def verifier_execute(self, pcode, exe, time, mem, args):
        """return a tuple (res:structures.case_result, verifier_output:str)
        
        no exceptions are raised"""
        global _cmd_vars
        user = None
        try:
            user = _cmd_vars["USER"]
            _cmd_vars["USER"] = os.geteuid()
        except KeyError:
            pass

        group = None
        try:
            group = _cmd_vars["GROUP"]
            _cmd_vars["GROUP"] = os.getegid()
        except KeyError:
            pass

        _cmd_vars["TIME"] = time
        _cmd_vars["MEMORY"] = mem

        _cmd_vars["DATADIR"] = os.path.abspath(pcode)

        ret = self._executor.run(exe, retrieve_stdout = True, extra_args = args)

        if user is not None:
            _cmd_vars["USER"] = user
        if group is not None:
            _cmd_vars["GROUP"] = group

        return ret



def _ch_add_executor(args):
    if len(args) == 1:
        raise UserError("Option {0} must be specified in the configuration file." . format(args[0]))
    _Executor(args)

def _ch_add_lang(args):
    if len(args) == 1:
        raise UserError("Option {0} must be specified in the configuration file." . format(args[0]))
    _Lang(args)

conf.register_handler("AddExecutor", _ch_add_executor)
conf.register_handler("AddLang", _ch_add_lang)

def _set_chroot_dir(arg):
    if len(arg) == 2:
        global _cmd_vars, _dir_temp
        if _dir_temp:
            raise conf.UserError("Option {0} must be set before TempDir" . format(arg[0]))
        if not os.path.isabs(arg[1]):
            raise conf.UserError("Option {0} takes an absolute path as argument" . format(arg[0]))
        _cmd_vars["CHROOT_DIR"] = arg[1]

def _set_temp_dir(arg):
    global _cmd_vars, _dir_temp, _dir_temp_abs, _prog_path, _prog_path_abs
    _dir_temp = arg[1]
    if "CHROOT_DIR" in _cmd_vars:
        if os.path.isabs(_dir_temp):
            raise conf.UserError("If ChrootDir is set, Option {0} takes a relative path as argument" . format(arg[0]))
        _dir_temp_abs = _join_path(_cmd_vars["CHROOT_DIR"], _dir_temp)
        _dir_temp = os.path.join('/', _dir_temp)
    else:
        if not os.path.isabs(_dir_temp):
            raise conf.UserError("Option {0} takes an absolute path as argument" . format(arg[0]))
        _dir_temp_abs = _dir_temp

    if not os.path.isdir(_dir_temp_abs):
        raise conf.UserError("path {0!r} is not a directory" . format(_dir_temp_abs))

    try:
        os.chmod(_dir_temp_abs,
                stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR |
                stat.S_IRGRP | stat.S_IWGRP | stat.S_IXGRP |
                stat.S_IROTH | stat.S_IWOTH | stat.S_IXOTH)
    except Exception as e:
        raise conf.UserError("failed to change permission for temporary directory: {0!r}" . format(e))

    _prog_path = _join_path(_dir_temp, _DEFAULT_PROG_NAME)
    _prog_path_abs = _join_path(_dir_temp_abs, _DEFAULT_PROG_NAME)

    _cmd_vars["WORKDIR"] = _dir_temp
    _cmd_vars["WORKDIR_ABS"] = _dir_temp_abs

def _set_lock_file(arg):
    if len(arg) == 2:
        global _lock_file_fd, _lock_file_obj
        _lock_file_obj = open(arg[1], "w")
        _lock_file_fd = _lock_file_obj.fileno()

def _set_user(arg):
    if len(arg) == 2:
        import pwd
        if arg[1][0] == '#':
            p = pwd.getpwuid(int(arg[1][1:]))
        else:
            p = pwd.getpwnam(arg[1])
        global _cmd_vars
        _cmd_vars["USER"] = p.pw_uid

def _set_group(arg):
    if len(arg) == 2:
        import grp
        if arg[1][0] == '#':
            g = grp.getgrgid(int(arg[1][1:]))
        else:
            g = grp.getgrnam(arg[1])
        global _cmd_vars
        _cmd_vars["GROUP"] = g.gr_gid

conf.simple_conf_handler("ChrootDir", _set_chroot_dir, required = False, no_dup = True, require_os = conf.REQUIRE_UNIX)
conf.simple_conf_handler("TempDir", _set_temp_dir, no_dup = True)
conf.simple_conf_handler("LockFile", _set_lock_file, required = False, no_dup = True, require_os = conf.REQUIRE_UNIX)
conf.simple_conf_handler("User", _set_user, required = False, no_dup = True, require_os = conf.REQUIRE_UNIX)
conf.simple_conf_handler("Group", _set_group, required = False, no_dup = True, require_os = conf.REQUIRE_UNIX)

