# $File: conf.py
# $Author: Jiakai <jia.kai66@gmail.com>
# $Date: Tue Nov 09 09:03:55 2010 +0800
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

"""parse orzoj configuration file and deal with initializing functions"""

import shlex, sys, platform

REQUIRE_WINDOWS = 1
REQUIRE_UNIX = 2

is_windows = (platform.system() == "Windows")
is_unix = (platform.system() == "Unix" or platform.system() == "Linux")

class _Handler:
    def __init__(self, func, no_dup, require_os):
        self.func = func
        self.used = False
        self.no_dup = no_dup
        self.require_os = require_os

_hd_dict = {}
_init_func = []
_end_func = []

class UserError(Exception):
    def __init__(self, msg):
        self.msg = msg


def register_handler(cmd, func, no_dup = False, require_os = 0):
    """register a command handler

    Keyword arguments:
    func -- the function which will be called when @cmd is found in the configuration file.
            It should take a list as argument, indicating the option and arguments (like argv of main() in C).
            The argument will be given None if no arguments are given (list = [optname, None])
            if @cmd is not found, the list will only contain option name

    require_os -- the ORing value of REQUIRE_* to indicate this option is only available on particular platforms

    exceptions IOError, KeyError, ValueError and Exception are caught by parse_file
    """
    global _hd_dict
    _hd_dict[cmd.lower()] = _Handler(func, no_dup, require_os)

def register_init_func(func):
    """register an initialization function, which will be called right after finishing parsing
    configuration file"""
    global _init_func
    _init_func.append(func)


def parse_file(filename):
    """parse the configuration file"""
    global _hd_dict, _init_func
    linenu = 0
    try:
        with open(filename, 'r') as f:
            while True:
                line = f.readline()
                if not line:
                    break

                linenu += 1

                while True:
                    while line and (line[-1] == '\n' or line[-1] == '-r'):
                        line = line[:-1]

                    if line and line[-1] == '\\':  # continue on next line
                        line = line[:-1] + f.readline()
                        linenu += 1
                    else:
                        break

                slist = shlex.split(line, comments = True)

                if not slist: # may be comment line or empty line
                    continue

                h = _hd_dict[slist[0].lower()]
                # options are case insensitive

                if h.used and h.no_dup:
                    raise UserError("duplicated option {0}" .
                            format(slist[0]))

                if h.require_os:
                    support = False

                    if (h.require_os & REQUIRE_WINDOWS) and is_windows:
                        support = True

                    if (h.require_os & REQUIRE_UNIX) and is_unix:
                        support = True

                    if not support:
                        raise UserError("Option {0} does not support your platform" .
                                format(slist[0]))

                h.used = True
                if len(slist) == 1:
                    slist.append(None)
                h.func(slist)

        for (cmd, func) in _hd_dict.iteritems():
            if not func.used:
                func.func([cmd])

        for i in _init_func:
            i()

        del _hd_dict
        del _init_func

    except IOError as e:
        sys.exit("failed to open file "
                "[errno {0}] [filename {1!r}]: {2}" .
                format(e.errno, e.filename, e.strerror))
    except KeyError as e:
        sys.exit("unknown configuration option on line {0}: {1}" .
                format(linenu, e.args[0]))
    except ValueError as e:
        sys.exit("error while parsing configuration file on line {0}: {1}" .
                format(linenu, e.args[0]))
    except UserError as e:
        sys.exit("error while parsing configuration file on line {0}: {1}" .
                format(linenu, e.msg))
    except Exception as e:
        sys.exit("error while parsing configuration file on line {0}: {1}" .
                format(linenu, e))


def simple_conf_handler(opt, call_back, default = None, required = True, no_dup = False, require_os = 0):
    """generate and register a configuration handler that takes exactly 1 argument
    

    Keyword arguments:
    call_back -- a function taking a list containing option name the argument as argument
    """
    def handler(args):
        if len(args) == 1:
            if default is None:
                if required:
                    raise UserError("Option {0} must be specified in the configuration file." .
                            format(args[0]))
                else:
                    return
            args.append(default)
            call_back(args)
        else:
            if len(args) != 2:
                raise UserError("Option {0} takes 1 argument, but {1} is(are) given." .
                        format(args[0], len(args) - 1))
            call_back(args)

    register_handler(opt, handler, no_dup, require_os)


