#!/usr/bin/python

# Generates a Mediawiki-compatible XML dump from a Sycamore wiki.
# Based on http://en.wikipedia.org/wiki/Help:Export
# Should be compatible with http://download.wikipedia.org/backup-index.html

# By default, only gives the most recent revision; give the "full" argument
# to get full revision history (big!)

# Ryan Tucker <rtucker@gmail.com>

import os
import os.path
import psycopg2
import sys
import time
import urllib

if len(sys.argv) < 2:
    sys.stderr.write('Including most recent revision only\n')
    max_revisions = 1
elif sys.argv[1] == 'full':
    sys.stderr.write('Printing full output!\n')
    max_revisions = 2**31-1

pause = 5

sys.stderr.write('Reniced to %i\n' % os.nice(19))

import _elementtree as ET

# Where am I?  Split argv[0] on /share and add the first half to the path.
sycamoreroot = sys.argv[0].split('/share')[0]
sys.path.append(sycamoreroot)
# Now import some stuff from Sycamore...
from Sycamore import config

timestring = time.ctime(os.path.getmtime(sys.argv[0]))
conn = psycopg2.connect(database=config.db_name, user=config.db_user, password=config.db_user_password)

def iter_pagelist(db):
    """Returns an iterator of pages in the Wiki, given a db"""
    cursor = db.cursor()
    cursor.execute("""
    SELECT DISTINCT propercased_name
    FROM
        curPages
    LEFT JOIN
        (SELECT pagename, may_read AS has_read_priv
                FROM pageacls
                WHERE groupname IN ('All')
        ) AS access
          ON (access.pagename = curpages.name)
    WHERE
        text NOT ILIKE '%#redirect %'
        AND
        edittime != 0
        AND (has_read_priv IS NULL OR has_read_priv)
    """)

    while True:
        result = cursor.fetchone()
        if not result:
            break
        yield result

def get_revisions(db, pagename, maxrev):
    """Given a db and a pagename (propercased_name), return an iterator with
       revision history, most recent first."""
    cursor = db.cursor()
    cursor.execute("""
        SELECT edittime, useredited, comment, userip, text
        FROM allpages
        WHERE propercased_name = %(pagename)s
        ORDER BY edittime DESC
        LIMIT %(limit)s
    """, dict(pagename=pagename, limit=maxrev))

    while True:
        result = cursor.fetchone()
        if not result:
            break
        yield result

def make_timestamp(ts):
    """Returns a timestamp of the form YYYY-MM-DDTHH:MM:SSZ given a unixtime"""
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(ts))

username_cache = {}

def get_username_by_useredited(db, useredited):
    if useredited in username_cache.keys():
        return username_cache[useredited]
    else:
        cursor = db.cursor()

        cursor.execute("""
            SELECT propercased_name
            FROM users
            WHERE id = %(useredited)s
        """, dict(useredited=useredited))

        username = cursor.fetchone()[0]
        username_cache[useredited] = username

        return username

# initial metadata
mediawiki = ET.Element("mediawiki",
                       xmlns="http://www.mediawiki.org/xml/export-0.4/",
                       version="0.4")
mediawiki.set("xmlns:xsi","http://www.w3.org/2001/XMLSchema-instance")
mediawiki.set("xsi:schemaLocation","http://www.mediawiki.org/xml/export-0.4/ http://www.mediawiki.org/xml/export-0.4.xsd")
mediawiki.set("xml:lang","en")

siteinfo = ET.SubElement(mediawiki, "siteinfo")
sitename = ET.SubElement(siteinfo, "sitename")
sitename.text = config.sitename
base = ET.SubElement(siteinfo, "base")
base.text = "http://%s/" % config.wiki_base_domain
generator = ET.SubElement(siteinfo, "generator")
generator.text="xml-dump-generate.py, rev %s, max_revisions %i" % (timestring, max_revisions)
case = ET.SubElement(siteinfo, "case")
case.text = "case-insensitive"
namespaces = ET.SubElement(siteinfo, "namespaces")
namespace_0 = ET.SubElement(namespaces, "namespace", key="0")
namespace_1 = ET.SubElement(namespaces, "namespace", key="1")
namespace_1.text = "Users"
namespace_2 = ET.SubElement(namespaces, "namespace", key="2")
namespace_2.text = "Wiki_Community"

# iterate through pages and revisions
for i in iter_pagelist(conn):
    pagename = i[0]
    page = ET.SubElement(mediawiki, "page")
    title = ET.SubElement(page, "title")
    title.text = pagename
    revs = get_revisions(conn, pagename, maxrev=max_revisions)
    counter = 0
    for j in revs:
        revision = ET.SubElement(page, "revision")
        timestamp = ET.SubElement(revision, "timestamp")
        timestamp.text = make_timestamp(j[0])
        contributor = ET.SubElement(revision, "contributor")
        username = ET.SubElement(contributor, "username")
        username.text = get_username_by_useredited(conn, j[1].strip())
        ip = ET.SubElement(contributor, "ip")
        ip.text = j[3]
        comment = ET.SubElement(revision, "comment")
        comment.text = j[2]
        text = ET.SubElement(revision, "text")
        text.text = j[4]
        text.set("xml:space", "preserve")
        time.sleep(pause)
        counter += 1
    sys.stderr.write("%s: Processed %i rev(s) for %s\n" % (time.strftime('%d-%H:%M:%S'), counter, pagename))

tree = ET.ElementTree(mediawiki)
tree.write(sys.stdout)

