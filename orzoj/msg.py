# $File: msg.py
# $Author: Jiakai <jia.kai66@gmail.com>
# $Date: Mon Nov 08 08:56:26 2010 +0800
#
# This file is part of orzoj
# 
# Copyright (C) <2010>  Jiakai <jia.kai66@gmail.com>
# 
# Orzoj is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# Orzoj is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with orzoj.  If not, see <http:#www.gnu.org/licenses/>.
#

"""definition of network messages"""

TELL_ONLINE_INTERVAL = 0.5

ERROR = 0xffffffff

PROTOCOL_VERSION = 0xff000001

# s2c: server to client(i.e. orzoj-judge)
# c2s: client to server

(
# packet format: (TELL_ONLINE)
# used when server or judge is wating for some task to be finished
TELL_ONLINE, # s2c, c2s

# packet format: (HELLO, id:string, PROTOCOL_VERSION:uint32_t,
# cnt:uint32_t, for(0<=i<cnt) supported language[i]:string)
HELLO, # c2s

# packet format: (DUPLICATED_ID)
DUPLICATED_ID, # s2c 
# packet format: (ID_TOO_LONG)
ID_TOO_LONG, # s2c 
# packet format: (CONNECT_OK)
CONNECT_OK, # s2c

# query system info ans give answers
# packet format: (QUERY_INFO, info:string),
# where info is something like "cpuinfo", "meminfo", etc.
QUERY_INFO, # s2c 
# packet format: (ANS_QUERY, ans:string)
ANS_QUERY, # c2s 

# prepare the judge process for a problem
# about to synchronize the data directory
# packet format: (PREPARE_DATA, problem code:string)
PREPARE_DATA, # s2c 
# packet format: (DATA_ERROR, reason:string)
DATA_ERROR, #c2s
# packet format:  (DATA_OK, cnt_case:uint32_t)
DATA_OK, # c2s 

# start judge process
# packet format: (START_JUDGE, language:string,
# source:string, input:string, output:string)
# if @input is empty string, meaning using stdin
# so is @output
START_JUDGE, # s2c 

# packet format: (START_JUDGE_OK)
START_JUDGE_OK, # c2s 
# packet format: (START_JUDGE_WAIT)
START_JUDGE_WAIT, # c2s 
# packet format: (COMPILE_SUCCEED)
COMPILE_SUCCEED, # c2s 
# packet format: (COMPILE_FAIL, reason:string)
COMPILE_FAIL, # c2s 
# packet format: (REPORT_CASE, result:case_result)
REPORT_CASE, # c2s 
# packet format: (REPORT_JUDGE_FINISH)
REPORT_JUDGE_FINISH, # c2s 

OFTP_BEGIN, 
OFTP_TRANS_BEGIN, 
OFTP_FILE_DATA, 
OFTP_FDATA_RECVED, 
OFTP_CHECK_OK, 
OFTP_CHECK_FAIL, 
OFTP_END, 
OFTP_SYSTEM_ERROR,

SYNCDIR_BEGIN, #s2c
# marks the beginning of synchronizing a directory
# packet format: (SYNCDIR_BEGIN, nfile:int, (filename[i]:string, checksum[i]:string))
SYNCDIR_FILELIST, #c2s
# packet format: (SYNCDIR_FILELIST, nfile:int, filenum[i]:int)
#            where filenum is the index of the file in the list sent by server
SYNCDIR_FTRANS, # s2c
# tell the client that filetrans is ready
# packet format: (SYNCDIR_FTRANS)
SYNCDIR_DONE # c2s
) = range(29)

def write_msg(conn, m, timeout = 0):
    conn.write_uint32(m, timeout)

def read_msg(conn, timeout = 0):
    return conn.read_uint32(timeout)

