# $File: core.py
# $Author: Jiakai <jia.kai66@gmail.com>
# $Date: Tue Sep 21 17:15:03 2010 +0800
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

import os.path, errno, shutil, time

try:
    import fcntl
except:
    pass

class Error(Exception):
    pass

from orzoj import conf, log, structures, msg
from orzoj.judge import limiter

_dir_temp = None  # relative to ChrootDir
_dir_temp_abs = None

_prog_path = None  # path of program being judged, without extention (relative to ChrootDir)
_prog_path_abs = None

_lock_file_obj = None
_lock_file_fd = None

_executor_dict = {}
lang_dict = {}

_cmd_vars = {"COMPILE_TIME" : msg.COMPILE_MAX_TIME * 1000}    # variables used in AddLimiter option

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
            p = os.path.join(_dir_temp_abs, i)
            if os.path.isdir(p) and not os.path.islink(p):
                shutil.rmtree(p)
            else:
                os.remove(p)
    except Exception as e:
        log.error("failed to clean temporary directory [{0!r}]: {1!r}" .
                format(_dir_temp_abs))
        raise Error

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

            l.run(_cmd_vars, stderr = limiter.SAVE_OUTPUT)

            if l.exe_status:
                if l.exe_status == structures.EXESTS_EXIT_NONZERO:
                    return (False, l.stderr)
                else:
                    return (False, "failed to compile: {0}: details: {1}" .
                            format(structures.EXECUTION_STATUS_STR[l.exe_status],
                                l.exe_extra_info))
            return (True, None)
        except limiter.SysError as e:
            return (False, "failed to compile: limiter error: {0}" .
                    format(e.msg))
        except Exception as e:
            return (False, "failed to compile: caught exception: {0!r}" .
                    format(e))

    def run(self, prog, stdin = None, stdout = None):
        """execute user's program @prog, stdin and stdout can be redirected to file
        allowed @stdin and @stdout values are the same as that of subprocess.Popen
        return an instance of structures.case_result
        
        no exceptions are raised"""

        global _cmd_vars
        res = structures.case_result()

        def mkerror(msg):
            res.exe_status = structures.EXESTS_SYSTEM_ERROR
            res.score = 0
            res.time = 0
            res.memory = 0
            res.extra_info = msg

        try:
            try:
                args = [_eval(i, prog) for i in self._args]
            except Exception:
                mkerror("failed to execute: executor configuration error")
                return res

            l = self._limiter
            _cmd_vars["TARGET"] = args

            l.run(_cmd_vars, stdin = stdin, stdout = stdout)

            res.exe_status = l.exe_status
            res.time = l.exe_time
            res.memory = l.exe_mem
            res.extra_info = l.exe_extra_info

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
        if len(args) != 5:
            raise conf.UserError("Option {0} takes four arguments, but {1} is(are) given" .
                    format(args[0], len(args) - 1))

        global _executor_dict, lang_dict

        if args[1] in lang_dict:
            raise conf.UserError("duplicated language: {0!r}" . format(args[1]))

        self._name = args[1]
        self._ext = args[2]

        if args[3] == "None":
            self._compiler = None
        else:
            if args[3] not in _executor_dict:
                raise conf.UserError("unknown compiler executor {0!r} for language {1!r}" .
                        format(args[3], args[1]))
            self._compiler = _executor_dict[args[3]]

        if args[4] not in _executor_dict:
            raise conf.UserError("unknown program executor {0!r} for language {1!r}" .
                    format(args[4], args[1]))
            self._executor = _executor_dict[args[4]]

        lang_dict[args[1]] = self

    def judge(self, snc, pcode, pconf, src, input, output):
        """@pcode: problem code
        @pconf: problem configuration (defined in probconf.py)
        may raise Error or snc.Error"""

        def _write_msg(m):
            msg.write_msg(snc, m)

        def _write_str(s):
            snc.write_str(s)

        def _write_uint32(v):
            snc.write_uint32(v)

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
                srcpath = _prog_path_abs + self._ext
                with open(srcpath, "w") as f:
                    f.write(src)

                _cmd_vars["MEMORY"] = 0
                _cmd_vars["DATADIR"] = os.path.abspath(pcode)

                if self._name in pconf.compiler:
                    (ok, info) = self._compiler.run_as_compiler(srcpath, pconf.compiler[self._name])
                else:
                    (ok, info) = self._compiler.run_as_compiler(srcpath)

                if not ok:
                    _write_msg(msg.COMPILE_FAIL)
                    _write_str(info)
                    return

            _write_msg(msg.COMPILE_SUCCEED)

            global _dir_temp_abs

            if pconf.extra_input:
                for i in pconf.extra_input:
                    shutil.copy(os.path.join(pcode, i), _dir_temp_abs)

            global _prog_path
            prob_result = structures.prob_result()
            for case in pconf.case:

                prog_fin_path = os.path.join(pcode, case.stdin)
                if not input:
                    prog_fin = open(prog_fin_path)
                else:
                    shutil.copy(prog_fin_path, os.path.join(_dir_temp_abs, pconf.input))
                    prog_fin = None

                if not output:
                    prog_fout_path = os.path.join(_dir_temp_abs, "output.{0}" .
                            format(time.time()))
                    prog_fout = open(prog_fout_path, "w")
                else:
                    prog_fout_path = os.path.join(_dir_temp_abs, output)
                    prog_fout = None

                _cmd_vars["TIME"] = case.time
                _cmd_vars["MEMORY"] = case.mem

                case_result = self._executor.run(_prog_path, stdin = prog_fin, stdout = prog_fout)

                if case_result.exe_status == structures.EXESTS_RIGHT:
                    (case_result.score, case_result.extra_info) = case.verify_func(case.score, prog_fin_path, 
                            os.path.join(pcode, case.stdout), prog_fout_path)
                    if case_result.score < case.score:
                        if case_result.score:
                            case_result.exe_status = structures.EXESTS_PARTIALLY_RIGHT
                        else:
                            case_result.exe_status = structures.EXESTS_WRONG_ANSWER

                    prob_result.total_score += case_result.score
                    prob_result.full_score += case.score

                    if case_result.score:
                        prob_result.total_time += case_result.time
                        if case_result.memory > prob_result.max_mem:
                            prob_result.max_mem = case_result.memory

                _write_msg(msg.REPORT_CASE)
                case_result.write(snc)

            _write_msg(msg.REPORT_JUDGE_FINISH)
            prob_result.write(snc)

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
        _cmd_vars["CHROOT_DIR"] = arg[1]

def _set_temp_dir(arg):
    global _cmd_vars, _dir_temp, _dir_temp_abs
    if "CHROOT_DIR" in _cmd_vars:
        _dir_temp = arg[1]
        _dir_temp_abs = os.path.join(_cmd_vars["CHROOT_DIR"], _dir_temp)
    else:
        _dir_temp = os.path.abspath(arg[1])
        _dir_temp_abs = _dir_temp

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

