# $File: probconf.py
# $Author: Jiakai <jia.kai66@gmail.com>
# $Date: Tue Dec 20 20:57:24 2011 +0800
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

import os.path, shlex
from xml.etree.ElementTree import ElementTree

from orzoj import log, structures, conf
from orzoj.judge import core, _filecmp

_PROBCONF_FILE = "probconf.xml"
_verifier_cache = None

class Error(Exception):
    def __init__(self, msg):
        self.msg = msg
    def __str__(self):
        return self.msg
    def __repr__(self):
        return self.msg

class _Parse_error(Exception):
    def __init__ (self, msg):
        self.msg = msg
    def __repr__(self):
        return self.msg
    def __str__(self):
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
                                # Note:
                                #   @info can be None
                                #   if @score is None, there is something wrong with the verifier
        self.extra_input = None # list, or None
        self.case = []          # list of Case_conf

        self._pcode = pcode
        self._parse()

    def _parse(self):

        pcode = self._pcode

        _parsers = {"1.0" : self._parse_1d0}

        try:
            tree = ElementTree()
            tree.parse(os.path.join(pcode, _PROBCONF_FILE))

            root = tree.getroot()
            if (root.tag != "orzoj-prob-conf"):
                raise _Parse_error("tag 'orzoj-prob-conf' not found")
            if "version" not in root.attrib:
                raise _Parse_error("version not found")
            v = root.attrib["version"]
            if v not in _parsers:
                raise _Parse_error("unknown version: {0!r}" . format(v))

            _parsers[v](root)


        except Exception as e:
            msg = "[pcode: {0!r}] failed to parse problem configuration file: {1}" . format(pcode, e)
            log.error(msg)
            raise Error(msg)

    def _parse_1d0(self, root): # for version 1.0
        global _verifier_cache
        for section in root:
            try:
                if section.tag == "compiler":
                    if self.compiler is None:
                        self.compiler = dict()
                    name = section.attrib["name"]
                    opt = _parse_compiler_opt(section.attrib["opt"])
                    if name not in self.compiler:
                        self.compiler[name] = list()
                    self.compiler[name].extend(opt)
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
                            lang = i.attrib["lang"]
                            try:
                                lang = core.lang_dict[lang]
                            except KeyError:
                                log.warning("language {0!r} for verifier not supported" . format(lang))
                                continue
                            time = 0
                            mem = 0
                            opt = None
                            try:
                                opt = _parse_compiler_opt(i.attrib["opt"])
                                time = int(i.attrib["time"])
                                mem = int(i.attrib["mem"])
                            except KeyError:
                                pass
                            
                            vf_path = os.path.abspath(os.path.join(_verifier_cache, self._pcode))
                            if "file" in i.attrib:
                                with open(os.path.join(self._pcode, i.attrib["file"]), "r") as f:
                                    src = f.read()
                            else:
                                src = i.text
                            if not src:
                                raise _Parse_error("no verifier source")
                            try:
                                ret = lang.verifier_compile(self._pcode, vf_path, src, opt)
                            except core.Error:
                                raise _Parse_error("failed to compile verifier")

                            if not ret[0]:
                                raise _Parse_error("failed to compile verifier: {0}" .
                                        format(ret[1]))

                            self.verify_func = _build_verifier(self._pcode, lang, time, mem, vf_path)
                            ok = True
                            break

                        if not ok:
                            raise _Parse_error("no usable verifier")
                    continue

                if section.tag == "extra":
                    if self.extra_input is None:
                        self.extra_input = list()
                    self.extra_input.append(section.attrib["file"])
                    continue

                if section.tag == "case":
                    case = Case_conf()
                    case.stdin = section.attrib["input"]
                    case.stdout = section.attrib["output"]
                    case.time = int(section.attrib["time"])
                    case.mem = int(section.attrib["mem"])
                    case.score = int(section.attrib["score"])
                    self.case.append(case)
                    continue
            except _Parse_error:
                raise
            except Exception as e:
                raise _Parse_error("error while parsing section {0!r}: {1}" . format(section.tag, e))

            raise _Parse_error("unknown tag: {0!r}" . format(section.tag))
        if self.verify_func is None:
            raise _Parse_error("no verifier specified")

def _std_verifier(score, fstdin, fstdout, fusrout):
    (ok, info) = _filecmp.filecmp(fstdout, fusrout)
    if ok:
        return (score, info)
    return (0, info)

def _build_verifier(pcode, lang, time, mem, verifier_path):
    """@lang is an instance of core._Lang"""
    def func(score, fstdin, fstdout, fusrout):
        score = str(score)
        fstdin = os.path.abspath(fstdin)
        fstdout = os.path.abspath(fstdout)
        fusrout = os.path.abspath(fusrout)
        res = lang.verifier_execute(pcode, verifier_path, time, mem, [score, fstdin, fstdout, fusrout])
        if res[0].exe_status != structures.EXESTS_NORMAL:
            return (None, "failed to execute verifier [status: {0}]: {1}" .
                    format(structures.EXECUTION_STATUS_STR[res[0].exe_status], res[0].extra_info))

        res = res[1]
        l = res.split(' ', 1)
        try:
            val = int(l[0])
        except Exception:
            log.error("[pcode {0!r}] verifier output is unrecognizable; original output of verifier: {1!r}" .
                    format(pcode, res))
            return (None, "unrecognizable verifier output")

        if len(l) == 1:
            return (val, None)
        return (val, l[1])

    return func

def _parse_compiler_opt(opt):
    return shlex.split(opt)

def _set_verifier_cache(arg):
    global _verifier_cache
    if not os.path.isdir(arg[1]):
        raise conf.UserError("verifier cache directory does not exist")
    _verifier_cache = arg[1]

conf.simple_conf_handler("VerifierCache", _set_verifier_cache)

