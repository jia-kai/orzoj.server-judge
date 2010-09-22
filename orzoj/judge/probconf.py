# $File: probconf.py
# $Author: Jiakai <jia.kai66@gmail.com>
# $Date: Wed Sep 22 23:42:55 2010 +0800
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

import os.path
from xml.etree.ElementTree import ElementTree

from orzoj import log, structures
from orzoj.judge import core, _filecmp

_PROBCONF_FILE = "probconf.xml"
_VERIFIER_PATH = "verifier"

class Error(Exception):
    pass

class _Parse_error(Exception):
    def __init__ (self, msg):
        self.msg = msg
    def __repr__(self):
        return self.msg

class Case_conf:
    def __init__(self):
        self.stdin = None       # string
        self.stdout = None      # string
        self.time = None        # integer, milliseconds
        self.mem = None         # integer, kb
        self.score = None       # integer

class Prob_conf:
    def __init__(self, pcode):
        """may raise Error"""
        self.compiler = None    # dict of list, or None
        self.verify_func = None # function(full score:int, stdinpath:string, stdoutpath:string, 
                                # useroutpath:string):(score:int, info:string)  
                                # Note: @info can be None
        self.extra_input = None # list, or None
        self.case = []          # list of Case_conf

        self._parse(filename)

    def _parse(self, pcode):

        _parsers = {"1.0" : self._parse_1d0}

        try:
            tree = ElementTree()
            tree.parse(os.path.join(pcode, _PROBCONF_FILE))

            for i in tree.getroot():
                if i.tag == "orzoj-prob-conf":
                    if "version" not in i.attrib:
                        raise _Parse_error("version not found")
                    v = i.attrib["version"]
                    if v not in _parsers:
                        raise _Parse_error("unknown version: {0!r}" . format(v))
                    _parsers[v](i)
                    return

            raise _Parse_error("tag 'orzoj-prob-conf' not found")

        except Exception as e:
            log.error("[pcode: {0!r}] failed to parse problem configuration file: {1!r}" .
                    format(pcode, e))
            raise Error

    def _parse_1d0(self, root): # for version 1.0
        for section in root:
            if section.tag == "compiler":
                t = self.compiler
                if t is None:
                    t = dict()
                    self.compiler = t
                name = t.find("name")
                if not name:
                    raise _Parse_error("no 'name' tag in the 'compiler' section")
                opt = t.find("opt")
                if not opt:
                    raise _Parse_error("no 'opt' tag in the 'compiler' section")
                t[name] = opt
                continue

            if section.tag == "verifier":
                if self.verify_func:
                    raise _Parse_error("duplicated tag: verifier");
                if "standard" in section.attrib:
                    self.verify_func = _std_verifier
                else:
                    ok = False
                    for i in section:
                        if i.tag != "source":
                            raise _Parse_error("unknown tag {0!r} in 'verifier'" . format(i.tag));
                        try:
                            lang = core.lang_dict[i.attrib["lang"]]
                        except KeyError:
                            continue
                        try:
                            time = int(i.attrib["time"])
                            mem = int(i.attrib["mem"])
                        except KeyError:
                            raise _Parse_error("no attribute 'time' or 'mem' for tag 'source'")

                        opt = None
                        try:
                            opt = i.attrib["opt"]
                        except KeyError:
                            pass
                        
                        try:
                            ret = lang.verifier_compile(pcode, _VERIFIER_PATH, i.text, opt)
                        except core.Error:
                            raise _Parse_error("failed to compile verifier")

                        if not ret[0]:
                            raise _Parse_error("failed to compile verifier: {0}" .
                                    format(ret[1]))

                        self.verify_func = _build_verifier(pcode, lang, ret[2], time, mem)
                        ok = True
                        break

                    if not ok:
                        raise _Parse_error("no usable verifier")
                continue

            if section.tag == "extra":
                if self.extra_input is None:
                    self.extra_input = list()
                self.extra_input.append(section.text)
                continue

            if section.tag == "case":
                case = Case_conf()
                try:
                    case.stdin = section.find("input").text
                    case.stdout = section.find("output").text
                    case.time = int(section.find("time").text)
                    case.mem = int(section.find("mem").text)
                    case.score = int(section.find("score").text)
                except ValueError as e:
                    raise _Parse_error("failed to convert to int: {0!r}" . format(e))
                except AttributeError as e:
                    raise _Parse_error("broken 'case' section")
                continue

            raise _Parse_error("unknown tag: {0!r}" . format(section.tag))

def _std_verifier(score, fstdin, fstdout, fusrout):
    (ok, info) = _filecmp.filecmp(fstdout, fusrout)
    if ok:
        return (score, info)
    return (0, info)

def _build_verifier(pcode, lang, exe, time, mem):
    """@lang is an instance of core._Lang"""
    def func(score, fstdin, fstdout, fusrout):
        res = lang.verifier_execute(pcode, exe, time, mem, [score, fstdin, fstdout, fusrout])
        if res[0].exe_status != structures.EXESTS_RIGHT:
            return (0, "failed to execute verifier [status: {0}]: {1}" .
                    format(structures.EXECUTION_STATUS_STR[res[0].exe_status], res[0].extra_info))

        res = res[1]
        l = res.split(' ', 1)
        try:
            val = int(l[0])
        except Exception:
            log.error("[pcode {0!r}] verifier output is unrecognizable: {1!r}" .
                    format(pcode, res))
            return (0, "unrecognized verifier output")

        if len(l) == 1:
            return (val, None)
        return (val, l[1])

