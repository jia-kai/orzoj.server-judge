/*
 * $File: _filecmp.c
 * $Author: Jiakai <jia.kai66@gmail.com>
 * $Date: Wed Dec 21 14:46:59 2011 +0800
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

#include <Python.h>

#include <stdio.h>
#include <string.h>
#include <errno.h>
#include <stdlib.h>
#include <ctype.h>

// args: (fstdout:str, fusrout:str)
static PyObject* filecmp(PyObject *self, PyObject *args);

static PyMethodDef
	methods_module[] = 
	{
		{"filecmp", (PyCFunction)filecmp, METH_VARARGS, NULL},
		{NULL, NULL, 0, NULL}
	};

const int BUF_SIZE = 32768;
struct Filecmp_ctx
{
	FILE *fobj[2];
	char *buf[2], *buf_end[2], *ptr[2];
};

const int CHAR_EOF = 256, CHAR_ERR = 257;
// return CHAR_EOF on end of file, CHAR_ERR on error
static int read_char(struct Filecmp_ctx *ctx, int p);

PyObject* filecmp(PyObject *self, PyObject *args)
{
#define RETURN(_ok_) \
	do \
	{ \
		int i; \
		for (i = 0; i < 2; i ++) \
		{ \
			if (ctx.fobj[i]) \
				fclose(ctx.fobj[i]); \
			if (ctx.buf[i]) \
				free(ctx.buf[i]); \
		} \
		return Py_BuildValue("(is)", (_ok_), info_buf); \
	} while(0)

	const char *fpath[2];
	char info_buf[256];
	int linenr = 1;
	struct Filecmp_ctx ctx;

	if (!PyArg_ParseTuple(args, "ss:filecmp", fpath, fpath + 1))
		return NULL;

	info_buf[0] = 0;

	memset(&ctx, 0, sizeof(ctx));

	ctx.fobj[0] = fopen(fpath[0], "rb");
	ctx.fobj[1] = fopen(fpath[1], "rb");

	if (!ctx.fobj[0] || !ctx.fobj[1])
	{
		snprintf(info_buf, sizeof(info_buf), "failed to open file: %s", strerror(errno));
		RETURN(0);
	}

	ctx.buf[0] = (char*)malloc(BUF_SIZE);
	ctx.buf[1] = (char*)malloc(BUF_SIZE);

	if (!ctx.buf[0] || !ctx.buf[1])
	{
		snprintf(info_buf, sizeof(info_buf), "failed to allocate memory: %s", strerror(errno));
		RETURN(0);
	}

	while (1)
	{
		int a = read_char(&ctx, 0), b = read_char(&ctx, 1);
		if (a == CHAR_ERR || b == CHAR_ERR)
		{
			strcpy(info_buf, "failed to read file");
			RETURN(0);
		}

		if (a != b)
		{
			if (a == ' ')
				a = read_char(&ctx, 0);
			if (a == '\r')
				a = read_char(&ctx, 0);

			if (b == ' ')
				b = read_char(&ctx, 1);
			if (b == '\r')
				b = read_char(&ctx, 1);

			if (a == CHAR_ERR || b == CHAR_ERR)
			{
				strcpy(info_buf, "failed to read file");
				RETURN(0);
			}

			if (a == CHAR_EOF || b == CHAR_EOF)
			{
				if (a != CHAR_EOF)
				{
					if (a != '\n')
						goto FAIL;
					a = read_char(&ctx, 0);
				}
				if (b != CHAR_EOF)
				{
					if (b != '\n')
						goto FAIL;
					b = read_char(&ctx, 1);
				}
				if (a != b)
					goto FAIL;
			}

			if (a != b || (a != '\n' && a != CHAR_EOF))
				goto FAIL;
		}

		if (a == CHAR_EOF)
			RETURN(1);

		if (a == '\n')
			linenr ++;

		continue;

FAIL:
		snprintf(info_buf, sizeof(info_buf), "file differs on line %d", linenr);
		RETURN(0);
	}

#undef RETURN
}

int read_char(struct Filecmp_ctx *ctx, int p)
{
#define fobj (ctx->fobj[p])
#define buf (ctx->buf[p])
#define buf_end (ctx->buf_end[p])
#define ptr (ctx->ptr[p])

	if (buf_end == ptr)
	{
		buf_end = buf + fread(buf, 1, BUF_SIZE, fobj);
		ptr = buf;

		if (buf_end == ptr)
			return ferror(fobj) ? CHAR_ERR : CHAR_EOF;
	}

	return *(ptr ++);

#undef fobj
#undef buf
#undef buf_end
#undef ptr
}


#ifndef PyMODINIT_FUNC	/* declarations for DLL import/export */
#define PyMODINIT_FUNC extern void
#endif

PyMODINIT_FUNC
init_filecmp(void)
{
	Py_InitModule3("_filecmp", methods_module, NULL);
}

