#!/usr/bin/env python

import sys
from orzoj.judge import _filecmp

if len(sys.argv) != 3:
    sys.exit("usage: {0} <file1> <file2>" . format(sys.argv[0]))

print repr(_filecmp.filecmp(sys.argv[1], sys.argv[2]))

