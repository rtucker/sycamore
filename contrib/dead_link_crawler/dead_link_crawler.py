#!/usr/bin/env python

# Given an URL for an XML dump, tests all the links and outputs which ones
# are bad, in wiki markup.  Uses Celery to parallelize the crawl.

# What you'll need to use this:
#   1) An XML dump (see share/xml-dump-generate.py)
#   2) celery
#   3) Some broker, e.g. RabbitMQ
#   4) Preferably memcached
#
# Usage:
#   1) Start celeryd
#   2) Run this script
#   3) cat out/*/* > a wiki page

# This is a proof of concept.  :-)

# Ryan Tucker <rtucker@gmail.com>, 2011 May 15

from celery.task import chord
from optparse import OptionParser

import datetime
import os
import pycurl
import sys
import time

from tasks import *

def parse_options():
    usage = "usage: %prog [options] [<path of XML dump>|<url of XML dump>]"
    description = "Given a Sycamore wiki dump, finds all of the embedded "
    description += "URLs and tests them for validity, outputting a list of "
    description += "pages with bad links."

    parser = OptionParser(usage=usage, description=description)

    (options, args) = parser.parse_args()

    if len(args) == 0:
        # No argument specified, assume stdin
        sourcefd = sys.stdin
        body = sourcefd.read()
        path = ''
    elif len(args) == 1:
        path = args[0]
        if os.path.exists(args[0]):
            # It is a file.
            sourcefd = open(args[0], 'r')
            body = sourcefd.read()
        else:
            # It is probably an URL.
            try:
                body, headers = fetch_url.delay(args[0]).get()
            except pycurl.error as err:
                parser.error("invalid url: %s" % err)

            http, status = headers.split('\n')[0].split(' ', 1)
            if not status.startswith('200'):
                parser.error("invalid url status: %s" % status)

    else:
        parser.error("incorrect number of arguments")

    if args[0].endswith('.bz2'):
        body = decompress.delay(body, extension='bz2').get()

    return (options, body)

def do_it():
    print("%s: Start" % datetime.datetime.now())
    options, xmlfile = parse_options()

    print("%s: Starting parse_pages." % datetime.datetime.now())
    result = parse_pages.delay(xmlfile,
                    callback=build_chord_for_page.subtask())
    print("%s: Waiting for parse_pages task to finish." %
                    datetime.datetime.now())
    result.wait()

    print("%s: End" % datetime.datetime.now())

if __name__ == '__main__':
    do_it()
