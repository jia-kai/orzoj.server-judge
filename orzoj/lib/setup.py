# $File: setup.py
# $Author: Jiakai <jia.kai66@gmail.com>
# $Date: Tue Sep 21 16:38:03 2010 +0800
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

from distutils.core import setup, Extension
import commands

cflags = ["-Wall"]
cflags.extend(commands.getoutput("pkg-config --cflags openssl").split())

module = Extension("orzoj._snc", sources = ["_snc.c"], 
        extra_compile_args = cflags,
        extra_link_args = commands.getoutput("pkg-config --libs openssl").split())

setup(name = "orzoj", ext_modules = [module])

