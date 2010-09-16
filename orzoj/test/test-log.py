#!/usr/bin/env python
import log, conf

def do_log():
    log.debug("debug")
    log.info("info")
    log.warning("warning")
    log.error("error")
    log.critical("critical")

conf.parse_file("test-log.conf")
do_log()
