# $File: conf.py
# $Author: Jiakai <jia.kai66@gmail.com>
# $Date: Wed Sep 15 10:29:29 2010 +0800
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

import shlex, sys

class _Handler:
    def __init__(self, func):
        self.func = func
        self.used = False

_hd_dict = {}
_init_func = []
_end_func = []

class UserError(Exception):
    def __init__(self, msg):
        self.msg = msg


def register_handler(cmd, func):
    """register a command handler

    Keyword arguments:
    func -- the function which will be called when @cmd is found in the configuration file.
            It should take a list as argument, indicating the options.
            The argument will be given None if @cmd is not found, and then default value should be used.

    exceptions IOError, KeyError and ValueError are caught
    """
    global _hd_dict
    _hd_dict[cmd.lower()] = _Handler(func)

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

                line = line.strip()

                if not line or line[0] == '#':  # ignore comment lines and empty lines
                    continue

                slist = line.split(None, 1)

                if not slist:
                    continue

                h = _hd_dict[slist[0].lower()]
                # options are case insensitive

                h.used = True
                if len(slist) == 1:
                    h.func([])
                else:
                    h.func(shlex.split(slist[1], True))

        for (cmd, func) in _hd_dict.iteritems():
            if not func.used:
                func.func(None)

        for i in _init_func:
            i()

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
        sys.exit("error while parsing configuration file on line {0}: {1!r}" .
                format(linenu, e))


class simple_conf_handler:
    def _handler(self, args):
        if args == None:
            if self.default == None:
                sys.exit("Option {0!r} must be specified in the configuration file." .
                        format(self.opt))
            self.call_back(self.default)
        else:
            if len(args) != 1:
                sys.exit("Option {0!r} takes 1 argument, but {1} is(are) given." .
                        format(self.opt, len(args)))
            self.call_back(args[0])

    def __init__(self, opt, call_back, default = None):
        """generate and register a simple configuration handler that takes only 1 argument
        

        Keyword arguments:
        call_back -- a function taken a string as argument, which will be called
                     with the argument value
        default -- if not set to None, it will be given as the value if @opt does not
                   appear in the configuration file
        
        """
        self.opt = opt
        self.call_back = call_back
        self.default = default
        register_handler(opt, self._handler)

