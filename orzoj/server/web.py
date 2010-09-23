# $File: web.py
# $Author: Jiakai <jia.kai66@gmail.com>
# $Date: Thu Sep 23 16:01:06 2010 +0800
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
# along with orzoj.  If not, see <http://www.gnu.org/licenses/>.
#

"""interface for communicating with orzoj-website

version 1:
    request to web:
        POST data=json.dumps({"thread_id" : int or string, "req_id" : int, "data" : str, "checksum" : str})  

        thread_id 
        where req_id is a strictly increasing integer
        checksum = sha1sum(str(thread_id) + str(req_id) + data + sha1sum(_dynamic_passwd + sha1sum(_static_passwd)))

    response from web:
        json.dumps({"status" : int, "data" : str, "checksum" : str})
        where status is either 0 or 1, 0 = success, 1 = error (data is a human-readable reason)
        checksum = sha1sum(str(thread_id) + str(req_id) + str(status) + data + sha1sum(_dynamic_passwd + sha1sum(_static_passwd)))

    thread_id:
        main thread: -1 (main thread only fetches task)
        judge thread: judge_id
        Note: On registration of judge, thread_id is the judge's identifier (string)
"""

from urllib2 import urlopen
from urllib import urlencode

class WebError(Exception):
    pass

def report_error(task, msg):
    """send a human-readable error message"""
    pass

def get_query_list():
    """return a list containing the queries for judge info.
    may raise Error"""
    return []

def register_new_judge(judge, query_ans):
    """register a new judge. @judge should be structures.judge,
    and query_ans should be a dictionary.
    may raise Error"""
    pass

def remove_judge(judge):
    pass

def fetch_task():
    """try to fetch a new task. return None if no new task available.
    this function does not raise exceptions"""
    return None

def report_no_judge(task):
    """tell the website that no judge supports the task's language
    this function does not raise exceptions"""
    pass

def report_no_data(task):
    """tell the website that there are no data for the task
    this function does not raise exceptions"""

def report_judge_waiting(task):
    """judge is waiting because it's serving another orzoj-server?"""
    pass

def report_compiling(task, judge):
    """now compiling @task on @judge"""
    pass

def report_compile_success(task):
    """successfully compiled"""
    pass

def report_compile_failure(task):
    """failed to compile"""
    pass

def report_case_result(task, result):
    pass

def report_prob_result(task, result):
    pass
