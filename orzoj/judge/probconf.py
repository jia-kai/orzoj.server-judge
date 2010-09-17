# $File: probconf.py
# $Author: Jiakai <jia.kai66@gmail.com>
# $Date: Fri Sep 17 17:38:01 2010 +0800
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

"""parse problem configuration file (XML)"""

class Error(Exception):
    def __init__ (self, msg):
        self.msg = msg

class Case_conf:
    def __init__(self):
        self.stdin = None       # string
        self.stdout = None      # string
        self.time = None        # integer, milliseconds
        self.mem = None         # integer, kb
        self.score = None       # integer

class Prob_conf:
    def __init__(self, filename):
        """may raise Error"""
        self.input = None       # string
        self.output = None      # string
        self.compiler = None    # dict, or None
        self.limiter = None     # dict, or None
        self.verify_func = None # function(full score:int, stdinpath:string, stdoutpath:string, useroutpath:string):(score:int, info:string)
        self.extra_input = None # list, or None
        self.case = []          # list of Case_conf
        self._parse(filename)

    def _parse(filename):

