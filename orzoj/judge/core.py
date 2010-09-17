# $File: core.py
# $Author: Jiakai <jia.kai66@gmail.com>
# $Date: Fri Sep 17 17:16:42 2010 +0800
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

from orzoj import conf, log
from orzoj.judge import limiter

_dir_chroot = None
_dir_temp = None
_exe_uid = None
_exe_gid = None

_compiler_dict = {}

class _Compiler:
    def __init__(self, args):
        if len(args) < 3:
            raise conf.UserError("Option AddCompiler takes at least three arguments")

        global _compiler_dict
        if args[0] in _compiler_dict:
            raise conf.UserError("duplicated compiler name: {0!r}" . foramt(args[0]))

        if args[1] not in limiter.limiter_dict:
            raise conf.UserError("unknown limiter {0!r} for compiler {1!r}" . 
                    format(args[1], args[0]))

        self._limiter = limiter.limiter_dict[args[1]]
        self._name = args[0]
        self._args = args[2:]

    def __run__(self, src):
        """compile the source code src and return a tuple (success, info),
        where success is a boolean value indicating whether it's compiled successfully,
        while info is the compiler output or a string indicating some system error (human readable)
            
        no exceptions are raised"""

        try:


