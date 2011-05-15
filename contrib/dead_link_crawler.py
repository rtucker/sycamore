#!/usr/bin/python

# Given an URL for an XML dump, tests all the links and outputs which ones
# are bad, in wiki markup.

# Ryan Tucker <rtucker@gmail.com>, 2011 May 15

from optparse import OptionParser
from StringIO import StringIO
from xml.etree.ElementTree import ElementTree

import bz2
import datetime
import dateutil.parser
import os
import pycurl
import re
import robotparser
import sys
import time
import urllib

DEBUG = False
VERSION = "2011051501"
USERAGENT = "sycamore_dead_link_crawler/%s (http://rocwiki.org/)" % VERSION

def get_url(url, referer=None, headonly=False):
    c = pycurl.Curl()
    c.setopt(pycurl.URL, str(url))
    c.setopt(pycurl.USERAGENT, USERAGENT)
    c.setopt(pycurl.FOLLOWLOCATION, True)
    if headonly:
        c.setopt(pycurl.NOBODY, True)
    if referer:
        c.setopt(pycurl.REFERER, str(referer))

    b = StringIO()
    h = StringIO()
    c.setopt(pycurl.WRITEFUNCTION, b.write)
    c.setopt(pycurl.HEADERFUNCTION, h.write)
    c.perform()
    b.seek(0)
    h.seek(0)
    return (b, h)

def parse_options():
    """
    Parses command line options, grabs the desired file, and decompresses
    it if necessary.

    Returns:
        (options, sourcefd)
        options: any keyword arguments (from optparse)
        sourcefd: a file-like object that XML can be read from
    """

    usage = "usage: %prog [options] [<path of XML dump>|<url of XML dump>]"
    description = "Given a Sycamore wiki dump, finds all of the embedded "
    description += "URLs and tests them for validity, outputting a list of "
    description += "pages with bad links."

    parser = OptionParser(usage=usage, description=description)

    parser.add_option('-d', '--debug', dest="debug", action="store_true",
                      help="Output lots of information to stderr",
                     )
    parser.add_option('--skip', dest="skip", action="append",
                      help="Hostnames to skip",
                      default=[],
                     )

    (options, args) = parser.parse_args()

    if options.debug:
        sys.stderr.write("Debug mode engaged.\n")
        sys.stderr.write("options: %s\n" % options)
        DEBUG = True

    if len(args) == 0:
        # No argument specified, assume stdin
        sourcefd = sys.stdin
    elif len(args) == 1:
        if os.path.exists(args[0]):
            # It is a file.
            sourcefd = open(args[0], 'r')
        else:
            # It is probably an URL.
            try:
                if DEBUG: sys.stderr.write("Retrieving %s\n" % args[0])
                sourcefd, headers = get_url(args[0])
            except pycurl.error as err:
                parser.error("invalid url: %s" % err)

            http, status = headers.readline().split(' ', 1)
            if not status.startswith('200'):
                parser.error("invalid url status: %s" % status)

    else:
        parser.error("incorrect number of arguments")

    if args[0].endswith('.bz2'):
        if DEBUG: sys.stderr.write("Decompressing %s\n" % args[0])
        sourcefd = StringIO(bz2.decompress(sourcefd.read()))
        sourcefd.seek(0)

    return (options, sourcefd)

def page_iterator(fd):
    """
    Given an XML document in a file-like object, yields tuples of:
        (title of page, datetime of page revision, content of page, url of page)
    For the most recent revision available.
    """
    namespace = "{http://www.mediawiki.org/xml/export-0.4/}"

    tree = ElementTree(file=fd)
    root = tree.getroot()

    siteinfo = root.find('%ssiteinfo' % namespace)
    sitebase = siteinfo.find('%sbase' % namespace).text
     
    if not root.tag == '%smediawiki' % namespace:
        raise ValueError("This does not appear to be a MediaWiki-style XML dump: %s" % root.tag)

    for page in root.getiterator(tag='%spage' % namespace):
        page_title = page.find('%stitle' % namespace).text
        page_timestamp = dateutil.parser.parse('1970-01-01T00:00:00Z')
        page_url = urllib.basejoin(sitebase, urllib.quote(page_title.replace(' ', '_')))
        text = None
        for revision in page.getiterator(tag='%srevision' % namespace):
            rev_timestamp = revision.find('%stimestamp' % namespace).text
            rev_timestamp = dateutil.parser.parse(rev_timestamp)
            if rev_timestamp > page_timestamp:
                page_timestamp = rev_timestamp
                text = revision.find('%stext' % namespace).text

        yield (page_title, page_timestamp, text, page_url)

def link_plucker(text):
    """
    Given a block of wiki-markup'd text, pulls out all the links and yields
    them as an iterator:
        (link url, link text)
    """
    for candidate in re.finditer("\[[^]]*\]", text):
        if candidate.group().startswith('[http'):
            # we have a linky
            bunch = candidate.group().strip('[]').split(' ', 1)
            if len(bunch) == 1:
                yield (bunch[0], '')
            else:
                yield (bunch[0], bunch[1])

def is_url_valid(url, referer=None):
    """
    Tests a URL.  Returns a tuple of:
        (true or false, status)
    """
    try:
        body, headers = get_url(url, referer, headonly=True)
    except pycurl.error as err:
        return (False, str(err))

    http, status = headers.readline().split(' ', 1)
    if not status.startswith('200'):
        return (False, status)

    return (True, status)

def do_it():
    options, xmlfile = parse_options()
    print("This is an auto-generated list of all off-site links that")
    print("failed to validate properly.")
    print("")
    print("Report start: %s" % datetime.datetime.now())
    print("")

    ROBOTMEMORY = {}
    HITMEMORY = {}

    if options.debug: DEBUG = True

    for title, timestamp, text, page_url in page_iterator(xmlfile):
        page_ok = True
        if DEBUG: sys.stderr.write("Testing links on %s\n" % page_url)
        for url, linktext in link_plucker(text):
            urlmethod, urltmp = urllib.splittype(url)
            urlhost = urllib.splithost(urltmp)[0]
            if urlhost not in ROBOTMEMORY and urlhost not in options.skip:
                sys.stderr.write("Checking robots.txt for %s\n" % urlhost)
                rp = robotparser.RobotFileParser()
                roboturl = urllib.basejoin('%s://%s' % (urlmethod, urlhost), 'robots.txt')
                try:
                    body, headers = get_url(roboturl, referer=page_url)
                    http, status = headers.readline().split(' ', 1)
                    if not status.startswith('200'):
                        # No robots.txt found, assuming OK
                        if DEBUG: sys.stderr.write("robots.txt couldn't be fetched: %s\n" % status)
                        ROBOTMEMORY[urlhost] = True
                    else:
                        rp.parse(body.readlines())
                        ROBOTMEMORY[urlhost] = rp.can_fetch(USERAGENT, url)
                except pycurl.error as err:
                    if DEBUG: sys.stderr.write("robots.txt couldn't be fetched: %s\n" % err)
                    ROBOTMEMORY[urlhost] = True
            if urlhost in ROBOTMEMORY and ROBOTMEMORY[urlhost] and urlhost not in options.skip:
                if urlhost in HITMEMORY:
                    if DEBUG: sys.stderr.write("Recently-hit host, waiting if needed")
                    while HITMEMORY[urlhost] > (datetime.datetime.now() - datetime.timedelta(seconds=10)):
                        time.sleep(1)
                        if DEBUG: sys.stderr.write(".")
                    if DEBUG: sys.stderr.write("\n")
                if DEBUG: sys.stderr.write("Pulling %s\n" % url)
                ok, status = is_url_valid(url, referer=page_url)
                HITMEMORY[urlhost] = datetime.datetime.now()
            elif urlhost not in options.skip:
                ok = False
                status = 'Denied by robots.txt'
            else:
                ok = True
                status = 'skipped'
            if not ok:
                if page_ok:
                    print(u" * [\"%s\"]" % title)
                    page_ok = False
                print(u"  * %s: [%s %s] (%s)" % (status.strip(), url, linktext, url))
            if DEBUG: sys.stderr.write("Result: %s, status %s\n" % (ok, status.strip()))

    print("")
    print("Report end: %s" % datetime.datetime.now())

if __name__ == '__main__':
    do_it()
