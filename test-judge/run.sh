#!/bin/bash -e
[ -f log ] && rm log

exec ./orzoj-judge -c test.conf -d

