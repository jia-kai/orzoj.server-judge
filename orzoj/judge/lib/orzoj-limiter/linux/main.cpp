/*
 * $File: main.cpp
 * $Author: Jiakai <jia.kai66@gmail.com>
 * $Date: Mon Nov 15 12:59:09 2010 +0800
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

#include "execute.h"
#include "exe_status.h"

#include <cstdio>
#include <cstring>
#include <cctype>
#include <cstdarg>
#include <cstdlib>

#include <errno.h>
#include <getopt.h>

#include <stdint.h>
#include <sys/socket.h>
#include <sys/un.h>

static const int SYSNR_MAX = 65536;

class Cleanup{};
class Error
{
	static const int MSG_LEN_MAX = 1024;
	static char msg[];
public:
	Error(const char *fmt, ...) __attribute__((format(printf, 2, 3)));
	const char *get_msg() {return msg;}
};
char Error::msg[Error::MSG_LEN_MAX];

static void usage(const char *argv0);
static int opensocket(const char *name);
static void report_result(int sockfd, int exe_status, const Execute_arg &arg);
static void init_syscall(Execute_arg &arg, const char *fname);
static int str2int(const char *str);

#define PROG_NAME "orzoj-limiter"

int main(int argc, char **argv)
{
	Execute_arg exe_arg;
	int sockfd = -1;
	FILE *syscall_flog = NULL;
	try
	{
		while (1)
		{
			static const struct option longopt[] = 
			{
				{"socket", required_argument, NULL, 0},
				{"chroot", required_argument, NULL, 1},
				{"chdir", required_argument, NULL, 2},
				{"time", required_argument, NULL, 3},
				{"hard-time", required_argument, NULL, 4},
				{"mem", required_argument, NULL, 5},
				{"nproc", required_argument, NULL, 6},
				{"user", required_argument, NULL, 7},
				{"group", required_argument, NULL, 8},
				{"stdout-max", required_argument, NULL, 9},
				{"stderr-max", required_argument, NULL, 10},
				{"syscall", required_argument, NULL, 11},
				{"gen-list", required_argument, NULL, 12},
				{"help", no_argument, NULL, 13},
				{"exec", no_argument, NULL, 14},
				{0, 0, 0, 0}
			};
			int opt = getopt_long(argc, argv, "", longopt, NULL);
			if (opt == -1)
			{
				fprintf(stderr, "%s: option --exec not found.\n", PROG_NAME);
				usage(PROG_NAME);
			}
			int exe_status;
			switch (opt)
			{
				case 0:
					if (sockfd != -1)
						throw Error("%s: duplicated --socket option", PROG_NAME);
					sockfd = opensocket(optarg);
					break;
#define SET(_id_, _arg_, _func_) \
				case _id_: \
						   exe_arg._arg_ = _func_(optarg); \
					break;

					SET(1, chroot, )
					SET(2, chdir, )
					SET(3, time, str2int)
					SET(4, hard_time, str2int)
					SET(5, mem, str2int)
					SET(6, nproc, str2int)
					SET(7, user, str2int)
					SET(8, group, str2int)
					SET(9, stdout_size, str2int)
					SET(10, stderr_size, str2int)
				case 11:
						init_syscall(exe_arg, optarg);
						break;
				case 12:
						if (syscall_flog)
							throw Error("%s: duplicated --gen-list option", PROG_NAME);
						syscall_flog = fopen(optarg, "w");
						if (!syscall_flog)
							throw Error("%s: failed to open file for --gen-list: %s (filename: %s)",
									PROG_NAME, strerror(errno), optarg);
						exe_arg.log_syscall = true;
						break;
				case 13:
						usage(PROG_NAME);
						break;
				case 14:
						if (sockfd == -1)
							throw Error("%s: option --socket not found", PROG_NAME);
						exe_status = execute(argv + optind, exe_arg);
						report_result(sockfd, exe_status, exe_arg);
						break;
				default:
						usage(PROG_NAME);
			}
		}
	} catch (Error e)
	{
		if (sockfd != -1)
		{
			exe_arg.extra_info = e.get_msg();
			try
			{
				report_result(sockfd, EXESTS_SYSTEM_ERROR, exe_arg);
			}
			catch (Cleanup)
			{
			}
		}
		else fprintf(stderr, "%s\n", e.get_msg());
	}
	catch (Cleanup)
	{
	}
	if (syscall_flog)
	{
		for (std::map<int, int>::iterator iter = exe_arg.syscall_cnt.begin();
				iter != exe_arg.syscall_cnt.end(); iter ++)
			fprintf(syscall_flog, "%d %d\n", iter->first, iter->second);
		fclose(syscall_flog);
	}
}

Error::Error(const char *fmt, ...)
{
	va_list ap;
	va_start(ap, fmt);
	vsnprintf(msg, MSG_LEN_MAX, fmt, ap);
	va_end(ap);
}

static void usage(const char *argv0)
{
	printf("Usage: %s [options] --exec <target> <arg1> <arg2> ... \n", argv0);
	printf("%s",
			"execute target program under limits.\n"
			"<target> is the path to target program, and <arg>s are the\n"
			"arguments passed to it."
			"\n\n"
			"where options are:\n"
			" --socket SOCKNAME  -- [required] use socket SOCKNAME for output\n"
			"                       an unsigned 32-bit integer will be writen\n"
			"                       to the socket indicating the execution\n"
			"                       status (defined in exe_status.h), followed\n"
			"                       by CPU time (in milliseconds) and memory (in kb)\n"
			"                       usage, then followed by the length of extra\n"
			"                       information and the information content (human-readable)\n"
			"                       of that length (all integers are 32-bit unsigned)\n"
			" --chroot CHROOTDIR -- chroot to CHROOTDIR before executing target\n"
			" --chdir WORKDIR    -- chdir to WORKDIR\n"
			" --time   TIME      -- set CPU time limit to TIME microseconds\n"
			" --hard-time TIME   -- set real time limit to TIME microseconds\n"
			" --mem MEM          -- set address size limit to MEM kb\n"
			" --nproc NPROC      -- set RLIMIT_NPROC to NPROC\n"
			" --user UID         -- execute target as user with id UID\n"
			" --group GID        -- execute target as group with id GID\n"
			" --syscall LIST     -- only allow system calls listed in the file LIST\n"
			"                       File format: each line contains two integers, nr and count,\n"
			"                       where nr is the system call number (see man 2 syscalls)\n"
			"                       and count is the maximal times to call that syscall. If count is\n"
			"                       negative, that syscall can be called for arbitrary times.\n"
			" --gen-list LIST    -- generate a list containing system calls called by target.\n"
			" --stdout-max SIZE  -- limit the max output to stdout to SIZE bytes\n"
			" --stderr-max SIZE  -- limit the max output to stderr to SIZE bytes\n"
			" --help             -- show this message and exit\n"
			"\n\nWritten by jiakai<jia.kai66@gmail.com>\n"
			"report bugs to: jia.kai66@gmail.com\n"
			);
	exit(1);
}

int opensocket(const char *name)
{
	int sockfd = socket(AF_UNIX, SOCK_STREAM, 0);
	if (sockfd < 0)
		throw Error("%s: failed to open socket: %s", PROG_NAME, strerror(errno));
	struct sockaddr_un adr_unix;
	memset(&adr_unix, 0, sizeof(adr_unix));
	adr_unix.sun_family = AF_UNIX;
	adr_unix.sun_path[0] = '@';
	strncpy(adr_unix.sun_path + 1, name,
			sizeof(adr_unix.sun_path) - 2);
	int len_unix = SUN_LEN(&adr_unix);
	adr_unix.sun_path[0] = 0;

	if (connect(sockfd, (sockaddr*)(&adr_unix), len_unix))
		throw Error("%s: failed to connect to socket: %s", PROG_NAME, strerror(errno));
	return sockfd;
}

void report_result(int sockfd, int exe_status, const Execute_arg &arg)
{
	int buflen = arg.extra_info.length() + 16;
	char *buf = new char[buflen];
	uint32_t val = exe_status;
	memcpy(buf, &val, 4);

	val = arg.result_time;
	memcpy(buf + 4, &val, 4);

	val = arg.result_mem;
	memcpy(buf + 8, &val, 4);

	val = arg.extra_info.length();
	memcpy(buf + 12, &val, 4);

	memcpy(buf + 16, arg.extra_info.c_str(), val);

	for (int tot = 0; tot < buflen; )
	{
		int t = write(sockfd, buf + tot, buflen - tot);
		if (t <= 0)
		{
			delete []buf;
			close(sockfd);
			throw Error("%s: failed to write to socket: %s", PROG_NAME, strerror(errno));
		}
		tot += t;
	}
	delete []buf;
	close(sockfd);
	throw Cleanup();
}

void init_syscall(Execute_arg &arg, const char *fname)
{
	if (arg.syscall_left)
		throw Error("%s: duplicated --syscall option", PROG_NAME);
	FILE *fin = fopen(fname, "r");
	if (!fin)
		throw Error("%s: failed to open syscall list: %s", PROG_NAME, strerror(errno));
	int max_nr = 0, nr, cnt;
	while (fscanf(fin, "%d%d", &nr, &cnt) == 2)
	{
		if (nr > SYSNR_MAX)
			throw Error("%s: syscall number too large: %d", PROG_NAME, nr);
		if (nr > max_nr)
			max_nr = nr;
	}
	arg.syscall_left_size = max_nr + 1;
	memset(arg.syscall_left = new int[max_nr + 1],
			0, sizeof(int) * (max_nr + 1));
	fclose(fin);
	fin = fopen(fname, "r");
	if (!fin)
		throw Error("%s: failed to open syscall list: %s", PROG_NAME, strerror(errno));
	while (fscanf(fin, "%d%d", &nr, &cnt) == 2)
	{
		if (nr > max_nr)
			throw Error("%s: syscall list chanded ?!", PROG_NAME);
		arg.syscall_left[nr] = cnt;
	}
}

int str2int(const char *str)
{
	int ret = 0;
	const char *str0 = str;
	while (*str)
	{
		if (!isdigit(*str))
			throw Error("%s: convert to \"%s\" to int: invalid char '%c' (%d)",
					PROG_NAME, str0, *str, *str);
		ret = ret * 10 + *(str ++) - '0';
	}
	return ret;
}

