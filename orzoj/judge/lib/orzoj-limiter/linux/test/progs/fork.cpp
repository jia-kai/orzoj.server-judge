#include <unistd.h>
#include <cstdlib>
#include <cstdio>
#include <sys/types.h>
#include <sys/wait.h>

int main()
{
	pid_t pid = fork();
	if (pid < 0)
	{
		perror("fork");
		exit(1);
	}
	if (pid == 0)
	{
		if (setsid() < 0)
			perror("setsid");
		printf("child process\n");
		while(1)
		{
			printf("child alive\n");
			sleep(1);
		}
	} else
	{
		sleep(1);
		printf("parent exited\n");
		_exit(0);
		wait(0);
		printf("child stopped.\n");
	}
}

