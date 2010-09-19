#include <pthread.h>
#include <cstdio>
#include <cstring>

void* thread(void*)
{
	printf("child created.\n");
	return NULL;
}

int main()
{
	pthread_t pt;
	int ret;
	if ((ret = pthread_create(&pt, NULL, thread, NULL)))
		printf("%s\n", strerror(ret));
	while (1);
}


