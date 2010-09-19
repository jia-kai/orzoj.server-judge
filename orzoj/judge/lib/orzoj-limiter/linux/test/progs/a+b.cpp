#include <cstdio>

int main()
{
	FILE *fin = fopen("a+b.in", "r"),
		 *fout = fopen("a+b.out", "w");
	int a, b;
	fscanf(fin, "%d%d", &a, &b);
	fprintf(fout, "%d\n", a + b);
	fclose(fin);
	fclose(fout);
}

