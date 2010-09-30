/*
 * $File: execute.cpp
 * $Author: Jiakai <jia.kai66@gmail.com>
 * $Date: Thu Sep 30 09:53:54 2010 +0800
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

#include <errno.h>
#include <cstdio>
#include <ctime>
#include <cmath>
#include <cstring>

#ifndef _GNU_SOURCE
#define _GNU_SOURCE
#endif
#include <unistd.h>
#include <signal.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <sys/time.h>
#include <sys/resource.h>
#include <pthread.h>
#include <sys/wait.h>
#include <sys/ptrace.h>
#include <sys/user.h>

static const std::string& _get_error_message(const char *func, int line);
#define get_error_message(_func_) \
	_get_error_message(_func_, __LINE__)

static const char* num2str(int n);

struct Thread_watch_arg
{
	bool error;
	pid_t pgid;
	int time;
	std::string error_str;
	Thread_watch_arg(pid_t pgid_, int time_) :
		error(false), pgid(pgid_), time(time_)
	{}
};
static void* thread_watch(void *arg);

struct Thread_limitout_arg
{
	bool error, exceeded;
	int fd, fd_target, size;
	pid_t pgid;
	std::string error_str;
	Thread_limitout_arg(pid_t pgid_) :
		error(false), exceeded(false), pgid(pgid_)
	{}
};
static void* thread_limitout(void *arg);

static void read_string(int fd, std::string &str);

int execute(char * const argv[], Execute_arg &arg)
{
	int pipe_msg[2], pipe_stdout[2], pipe_stderr[2];
	if (pipe2(pipe_msg, O_CLOEXEC))
	{
		arg.extra_info = get_error_message("pipe2");
		return EXESTS_SYSTEM_ERROR;
	}

	if (arg.stdout_size && pipe(pipe_stdout))
	{
		arg.extra_info = get_error_message("pipe");
		return EXESTS_SYSTEM_ERROR;
	}

	if (arg.stderr_size && pipe(pipe_stderr))
	{
		arg.extra_info = get_error_message("pipe");
		return EXESTS_SYSTEM_ERROR;
	}

	pid_t pid = fork();
	if (pid < 0)
	{
		arg.extra_info = get_error_message("fork");
		return EXESTS_SYSTEM_ERROR;
	}

	if (pid == 0)
	{
#define ERROR(_func_) \
		do \
		{ \
			const std::string &msg = get_error_message(_func_); \
			write(pipe_msg[1], msg.c_str(), msg.length()); \
			_exit(-1); \
		} while (0)
		close(pipe_msg[0]);

		if (arg.stdout_size)
		{
			close(pipe_stdout[0]);
			if (dup2(pipe_stdout[1], STDOUT_FILENO) < 0)
				ERROR("dup2");
		}

		if (arg.stderr_size)
		{
			close(pipe_stderr[0]);
			if (dup2(pipe_stderr[1], STDERR_FILENO) < 0)
				ERROR("dup2");
		}

		if (setsid() < 0)
			ERROR("setsid");

		if (!arg.chroot.empty())
		{
			if (chroot(arg.chroot.c_str()))
				ERROR("chroot");
			if (chdir("/"))
				ERROR("chdir");
		}

		if (!arg.chdir.empty())
			if (chdir(arg.chdir.c_str()))
				ERROR("chdir");

		if (arg.group)
			if (setresgid(arg.group, arg.group, arg.group))
				ERROR("setresgid");

		if (arg.user)
			if (setresuid(arg.user, arg.user, arg.user))
				ERROR("setreugid");

		struct rlimit limit;

		if (arg.nproc)
		{
			limit.rlim_cur = limit.rlim_max = arg.nproc;
			if (setrlimit(RLIMIT_NPROC, &limit))
				ERROR("setrlimit");
		}

		if (arg.mem)
		{
			limit.rlim_cur = limit.rlim_max = arg.mem * 1024;
			if (setrlimit(RLIMIT_AS, &limit))
				ERROR("setrlimit");
		}

		if (arg.time)
		{
			limit.rlim_cur = limit.rlim_max = (arg.time - 1) / 1000 + 1;
			if (setrlimit(RLIMIT_CPU, &limit))
				ERROR("setrlimit");
		}
		
		if (arg.syscall_left || arg.log_syscall)
		{
			if (ptrace(PTRACE_TRACEME, 0, 0, 0))
				ERROR("ptrace");
			// we do not need to send this process a signal
			// because we'll call execv later.
		}

		execv(argv[0], argv);

		ERROR("execv");
#undef ERROR
	} else // parent process
	{
#define ERROR(_func_) \
		do \
		{ \
			arg.extra_info = get_error_message(_func_); \
			return EXESTS_SYSTEM_ERROR; \
		} while (0)

		close(pipe_msg[1]);

		pthread_t pt_watch;
		Thread_watch_arg thread_watch_arg(pid, arg.hard_time);
		if (arg.hard_time)
		{
			int ret;
			if ((ret = pthread_create(&pt_watch, NULL, thread_watch, &thread_watch_arg)))
				ERROR("pthread_create");
		}

		Thread_limitout_arg limit_stdout_arg(pid), limit_stderr_arg(pid);
		if (arg.stdout_size)
		{
			close(pipe_stdout[1]);
			limit_stdout_arg.fd = pipe_stdout[0];
			limit_stdout_arg.fd_target = STDOUT_FILENO;
			limit_stdout_arg.size = arg.stdout_size;
			int ret;
			pthread_t pt;
			if ((ret = pthread_create(&pt, NULL, thread_limitout, &limit_stdout_arg)))
				ERROR("pthread_create");
		}

		if (arg.stderr_size)
		{
			close(pipe_stderr[1]);
			limit_stderr_arg.fd = pipe_stderr[0];
			limit_stderr_arg.fd_target = STDERR_FILENO;
			limit_stderr_arg.size = arg.stderr_size;
			int ret;
			pthread_t pt;
			if ((ret = pthread_create(&pt, NULL, thread_limitout, &limit_stderr_arg)))
				ERROR("pthread_create");
		}

		int status, sig = -1;
		struct rusage ru;

		if (arg.syscall_left || arg.log_syscall)
		{
			// check for system calls
			bool first_stop = true;
			while (1)
			{
				if (wait4(pid, &status, 0, &ru) < 0)
				{
					if (arg.hard_time)
						pthread_cancel(pt_watch);
					ERROR("wait4");
				}
				if (WIFSTOPPED(status))
				{
					if (WSTOPSIG(status) == SIGTRAP)
					{
						if (!first_stop) // first stop is caused by execv and we don't care
						{
							struct user_regs_struct regs;
							if (ptrace(PTRACE_GETREGS, pid, NULL, &regs))
							{
								if (arg.hard_time)
									pthread_cancel(pt_watch);
								ptrace(PTRACE_KILL, pid, NULL, NULL);
								wait(NULL);
								ERROR("ptrace");
							}


							int scnr = regs.orig_eax; // system call number

							if (arg.syscall_left)
							{
								if (scnr >= arg.syscall_left_size ||
										!arg.syscall_left[scnr])
								{
									ptrace(PTRACE_KILL, pid, NULL, NULL);
									if (arg.hard_time)
										pthread_cancel(pt_watch);
									wait(NULL);
									arg.extra_info = "disallowed system call: ";
									arg.extra_info.append(num2str(scnr));
									return EXESTS_ILLEGAL_CALL;
								} else arg.syscall_left[scnr] --;
							}

							if (arg.log_syscall)
							{
								if (arg.syscall_cnt.find(scnr) == arg.syscall_cnt.end())
									arg.syscall_cnt[scnr] = 1;
								else arg.syscall_cnt[scnr] ++;
							}
						} else first_stop = false;
					} else
					{
						sig = WSTOPSIG(status);
						ptrace(PTRACE_KILL, pid, NULL, NULL);
						break;
					}
				} else break;
				ptrace(PTRACE_SYSCALL, pid, NULL, NULL);
			}
		} else if (wait4(pid, &status, 0, &ru) < 0)
		{
			if (arg.hard_time)
				pthread_cancel(pt_watch);
			ERROR("wait4");
		}

		killpg(pid, SIGKILL);
		kill(pid, SIGKILL);
		// it may fork a child
		// it can also setsid or setpgid, so it's necessary to 
		// ptrace and limit nproc

		if (arg.hard_time)
		{
			pthread_cancel(pt_watch);

			if (thread_watch_arg.error)
			{
				arg.extra_info = thread_watch_arg.error_str;
				return EXESTS_SYSTEM_ERROR;
			}
		}

		if (arg.stdout_size)
		{
			close(pipe_stdout[0]);
			if (limit_stdout_arg.error)
			{
				arg.extra_info = limit_stdout_arg.error_str;
				return EXESTS_SYSTEM_ERROR;
			}
			if (limit_stdout_arg.exceeded)
			{
				arg.extra_info = "stdout size exceeded";
				return EXESTS_SIGKILL;
			}
		}

		if (arg.stderr_size)
		{
			close(pipe_stderr[0]);
			if (limit_stderr_arg.error)
			{
				arg.extra_info = limit_stderr_arg.error_str;
				return EXESTS_SYSTEM_ERROR;
			}
			if (limit_stderr_arg.exceeded)
			{
				arg.extra_info = "stderr size exceeded";
				return EXESTS_SIGKILL;
			}
		}

		read_string(pipe_msg[0], arg.extra_info);
		if (!arg.extra_info.empty())
			return EXESTS_SYSTEM_ERROR;

		arg.result_time = ru.ru_utime.tv_sec * 1000000 + ru.ru_utime.tv_usec +
			ru.ru_stime.tv_sec * 1000000 + ru.ru_stime.tv_usec;
		arg.result_mem = ((unsigned long long)ru.ru_minflt *
				(unsigned long long)sysconf(_SC_PAGESIZE)) / 1024ull;

		if (arg.time && arg.result_time > arg.time * 1000)
			return EXESTS_TLE;

		if (WIFSIGNALED(status) || sig != -1)
		{
			if (sig == -1)
				sig = WTERMSIG(status);

			if (sig == SIGKILL)
				return EXESTS_SIGKILL;
			// it may be killed by thread_watch beacause of real time limit

			if (sig == SIGSEGV)
				return EXESTS_SIGSEGV;
			arg.extra_info = "terminated by signal ";
			arg.extra_info.append(strsignal(sig)).append("(").append(num2str(sig))
				.append(")");
			return EXESTS_SIGNAL;
		}

		if (WIFEXITED(status) && WEXITSTATUS(status))
		{
			arg.extra_info = std::string("exit code: ") + num2str(WEXITSTATUS(status));
			return EXESTS_EXIT_NONZERO;
		}

		return 0;

#undef ERROR
	}
}

const std::string& _get_error_message(const char *func, int line)
{
	static std::string msg;
	msg = "error while calling ";
	msg.append(func).append(" at ").append(__FILE__)
		.append(":").append(num2str(line)).append(" : ")
		.append(strerror(errno));
	return msg;
}

void* thread_watch(void *arg0)
{
	pthread_setcanceltype(PTHREAD_CANCEL_ASYNCHRONOUS, NULL);
	Thread_watch_arg &arg = *static_cast<Thread_watch_arg*>(arg0);
#define ERROR(_func_) \
	do \
	{ \
		arg.error_str = get_error_message(_func_); \
		arg.error = true; \
		killpg(arg.pgid, SIGKILL); \
		kill(arg.pgid, SIGKILL); \
		return NULL; \
	} while (0)

	timespec tp;
	if (clock_gettime(CLOCK_MONOTONIC, &tp))
		ERROR("clock_gettime");
	tp.tv_sec += arg.time / 1000;
	tp.tv_nsec += (arg.time % 1000) * 1000000;
	if (tp.tv_nsec >= 1000000000)
		tp.tv_sec ++, tp.tv_nsec -= 1000000000;

	while (clock_nanosleep(CLOCK_MONOTONIC, TIMER_ABSTIME,
				&tp, NULL))
		if (errno != EINTR)
			ERROR("clock_nanosleep");

	killpg(arg.pgid, SIGKILL);
	kill(arg.pgid, SIGKILL);
	return NULL;
#undef ERROR
}

void* thread_limitout(void *arg0)
{
	Thread_limitout_arg &arg = *static_cast<Thread_limitout_arg*>(arg0);
	const int BUF_SIZE = 4096;
	char buf[BUF_SIZE];
	int tot = 0;
	while (1)
	{
		ssize_t s = read(arg.fd, buf, BUF_SIZE);
		if (s > 0)
		{
			tot += s;
			if (tot > arg.size)
			{
				arg.exceeded = true;
				killpg(arg.pgid, SIGKILL);
				kill(arg.pgid, SIGKILL);
			}
			for (ssize_t cnt = 0; cnt < s; )
			{
				ssize_t t = write(arg.fd_target, buf, s - cnt);
				if (t < 0)
				{
					arg.error = true;
					arg.error_str = "failed to write: ";
					arg.error_str.append(strerror(errno));
					killpg(arg.pgid, SIGKILL);
					kill(arg.pgid, SIGKILL);
					return NULL;
				}
				cnt += t;
			}
		} else return NULL;
	}
}

void read_string(int fd, std::string &str)
{
	str.clear();
	const int BUF_LEN = 1024;
	static char buf[BUF_LEN];
	ssize_t ret;
	while ((ret = read(fd, buf, BUF_LEN)) > 0)
		str.append(buf, ret);
}

const char* num2str(int n)
{
	static char buf[sizeof(int) * 8]; // sufficient
	sprintf(buf, "%d", n);
	return buf;
}

