#!/bin/bash -e
[ -f log ] && rm log

exec ./orzoj-server -c test.conf -d

