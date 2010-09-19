/*
 * $File: execute.h
 * $Author: Jiakai <jia.kai66@gmail.com>
 * $Date: Fri Sep 17 20:13:36 2010 +0800
 */
/*
This file is part of orzoj

Copyright (C) <2010>  Jiakai <jia.kai66@gmail.com>

Orzoj is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

Orzoj is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with orzoj.  If not, see <http://www.gnu.org/licenses/>.
*/

#ifndef _HEADER_EXECUTE_
#define _HEADER_EXECUTE_

#include <string>
#include <map>

#include <cstdio>

struct Execute_arg
{
	std::string
		chroot, chdir, extra_info;
	// extra_info will be for retrieving message from execute()
	int time, hard_time, mem, user, group, nproc,
		*syscall_left, syscall_left_size, // set syscall_left to NULL if do not limit syscall
		stdout_size, stderr_size;

	bool log_syscall;
	std::map<int, int> syscall_cnt;

	int result_time, result_mem;
	// result_time is in microseconds
	Execute_arg():
		time(0), hard_time(0), mem(0), user(0), group(0), nproc(0),
		syscall_left(NULL), syscall_left_size(0),
		stdout_size(0), stderr_size(0),
		log_syscall(false),
		result_time(0), result_mem(0)
	{}
};

int execute(char * const argv[], Execute_arg &arg);

#endif

