#include <cstdio>
#include <unistd.h>

int main()
{
	uid_t uidr, uide, uids;
	getresuid(&uidr, &uide, &uids);
	printf("resuid: %d %d %d\n", uidr, uide, uids);

	gid_t gidr, gide, gids;
	getresgid(&gidr, &gide, &gids);
	printf("resgid: %d %d %d\n", gidr, gide, gids);

	printf("pid: %d\n", getpid());
	printf("pgid: %d\n", getpgrp());

	printf("cwd: %s\n", get_current_dir_name());
}

