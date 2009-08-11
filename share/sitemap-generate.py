#!/usr/bin/python

# Generates a Sitemap for a Sycamore wiki.
# Run this hourly, and stick the output somewhere accessable as
# http://yourwiki.org/sitemap.xml ... also, point at it with a
# Sitemap: http://... line in your robots.txt.

# Ryan Tucker <rtucker@gmail.com>

import psycopg2
import sys
import time
import urllib

# Where am I?  Split argv[0] on /share and add the first half to the path.
sycamoreroot = sys.argv[0].split('/share')[0]
sys.path.append(sycamoreroot)
# Now import some stuff from Sycamore...
from Sycamore import config

ignore_startswith = ('wiki settings/', 'templates/', 'users/')
ignore_pages = ('wiki settings', 'templates', 'wanted pages', 'bookmarks', 'recent changes', 'user statistics', 'events board', 'all pages', 'random pages', 'orphaned pages', 'interwiki map')

low_priority_startswith = ('wiki community/', 'xyzzy/')
low_priority_pages = ('xyzzy', 'xyzzy')

high_priority_startswith = ('xyzzy/', 'xyzzy/')
high_priority_pages = ('front page', 'xyzzy')


def getpriority(name):
    lower_name = name.lower()

    if lower_name in ignore_pages:
        return 0
    for startname in ignore_startswith:
        if lower_name.startswith(startname):
            return 0

    if lower_name in low_priority_pages:
        return 0.3
    for startname in low_priority_startswith:
        if lower_name.startswith(startname):
            return 0.3

    if lower_name in high_priority_pages:
        return 0.9
    for startname in high_priority_startswith:
        if lower_name.startswith(startname):
            return 0.9

    return 0.5

def makelist(cursor):
    cursor.execute("""
    SELECT DISTINCT propercased_name, edittime
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
        AND
        propercased_name NOT LIKE '%/Talk'
        AND (has_read_priv IS NULL OR has_read_priv)
    ORDER BY edittime DESC
    """)
    results = cursor.fetchall()
   
    batch = ''

    for entry in results:
        name = entry[0] 
        lower_name = name.lower()

        priority = getpriority(name)
        if priority == 0:
            continue
        lastmod_time = time.strftime('%Y-%m-%d', time.localtime(entry[1]))
        lastmod_timestamp = int(entry[1])
        curtime_timestamp = int(time.time())
        lastmod_hoursago = (curtime_timestamp - lastmod_timestamp)/60/60

        if lastmod_hoursago < 24:
            frequency = 'hourly'
        elif lastmod_hoursago < 24*7:
            frequency = 'daily'
        elif lastmod_hoursago < 24*7*4:
            frequency = 'weekly'
        elif lastmod_hoursago < 24*7*4*28:
            frequency = 'monthly'
        else:
            frequency = 'yearly'

        batch += "<url><loc>http://%s/%s</loc><lastmod>%s</lastmod><priority>%2.1f</priority><changefreq>%s</changefreq><!-- %i hours ago --></url>\n" % (config.wiki_base_domain, urllib.quote(name.replace(' ', '_')), lastmod_time, priority, frequency, lastmod_hoursago)

    return batch

def __main__():
    conn = psycopg2.connect(database=config.db_name, user=config.db_user, password=config.db_user_password)
    cursor = conn.cursor()

    sys.stdout.write('<?xml version="1.0" encoding="UTF-8"?>\n')
    sys.stdout.write('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.sitemaps.org/schemas/sitemap/0.9 http://www.sitemaps.org/schemas/sitemap/0.9/sitemap.xsd">\n')
    sys.stdout.write(makelist(cursor))
    sys.stdout.write('</urlset>\n')

__main__()

