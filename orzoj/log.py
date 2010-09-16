# $File: log.py
# $Author: Jiakai <jia.kai66@gmail.com>
# $Date: Sat Sep 11 20:32:56 2010 +0800
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

"""orzoj logging system"""

import logging, logging.handlers, sys
import conf

_logger = logging.getLogger()

debug   = _logger.debug
info    = _logger.info
warning = _logger.warning
error   = _logger.error
critical= _logger.critical


_filename = ''
_level = ''
_max_bytes = 0
_backup_count = 0

_LEVELS = {'debug': logging.DEBUG,
        'info': logging.INFO,
        'warning': logging.WARNING,
        'error': logging.ERROR,
        'critical': logging.CRITICAL}

def _seg_filename(arg):
    global _filename
    _filename = arg

def _seg_level(arg):
    global _LEVELS, _level
    if arg not in _LEVELS:
        raise conf.UserError("unknown LogLevel: {0}" . format(arg))
    _level = _LEVELS[arg]

def _seg_max_bytes(arg):
    global _max_bytes
    _max_bytes = int(arg)
    if _max_bytes < 0:
        raise conf.UserError("LogMaxBytes can't be less than 0")

def _seg_backup_count(arg):
    global _backup_count
    _backup_count = int(arg)
    if _backup_count < 0:
        raise conf.UserError("LogBackupCount can't be less than 0")

def _init():
    global _logger, _filename, _level, _max_bytes, _backup_count
    handler = logging.handlers.RotatingFileHandler(
            _filename, maxBytes = _max_bytes, backupCount = _backup_count)
    handler.setFormatter(logging.Formatter(
        "[%(asctime)s] [%(levelname)s] from %(module)s.%(funcName)s at %(filename)s:%(lineno)d :\n%(message)s"))
    _logger.setLevel(_level)
    _logger.addHandler(handler)


conf.simple_conf_handler("LogFile", _seg_filename)
conf.simple_conf_handler("LogLevel", _seg_level, 'info')
conf.simple_conf_handler("LogMaxBytes", _seg_max_bytes, '0')
conf.simple_conf_handler("LogBackupCount", _seg_backup_count, '0')
conf.register_init_func(_init)
