# $File: setup.py
# $Author: Jiakai <jia.kai66@gmail.com>
# $Date: Tue Dec 20 21:30:18 2011 +0800
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
import commands, platform

cflags = None
libs = None

if platform.system() == "Linux":
    cflags = ["-Wall", "-DORZOJ_DEBUG"]
    cflags.extend(commands.getoutput("pkg-config --cflags openssl").split())
    libs = commands.getoutput("pkg-config --libs openssl").split()


module = Extension("orzoj._snc", sources = ["_snc.c"], 
        extra_compile_args = cflags,
        extra_link_args = libs)

setup(name = "orzoj", ext_modules = [module])

