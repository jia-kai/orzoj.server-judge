#include <cstdio>

int f(int n)
{
	if (n <= 1)
		return 1;
	if (n == 2)
		return 2;
	return f(n - 1) + f(n - 2);
}

int main(int argc, char **argv)
{
	int n;
	scanf("%d", &n);
	printf("stdout: %d\n", f(n));
	fprintf(stderr, "this is stderr.\n");
	printf("args:\n");
	while (*argv)
		printf("%s\n", *(argv ++));
}

