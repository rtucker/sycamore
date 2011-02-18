#!/usr/bin/python

# Returns a list of search suggestions in json format.
# Suitable for opensearch support.

# Timeout functions from:
# http://nick.vargish.org/clues/python-tricks.html

# Test me like:
#   http://rocwiki.org/wiki/cgi/opensearch-suggest.py?format=list&query=tap

# Ryan Tucker <rtucker@gmail.com>, November 15 2008
# 2008/12/11: Added some timeouts to limit database queries to three seconds,
#             to avoid problems under load.  -rt
# 2009/01/02: Revised to use xapian, for more efficiency
# 2009/08/10: Cleaning up to make less rocwiki-specific before importing to git

maxresults = 10
memcachedtag = 'oss-028-'

# Imports
import cgi
import cgitb; cgitb.enable(display=0, logdir="/tmp", format='text')
import psycopg2
import signal
import simplejson as json
import string
import sys
import time
import urllib
#import xapian

# Where am I?  Split argv[0] on /share and add the first half to the path.
sycamoreroot = sys.argv[0].split('/share')[0]
sys.path.append(sycamoreroot)
# Now import some stuff from Sycamore...
from Sycamore import config
from Sycamore.support import memcache

databases = [config.search_db_location + '/title']

# timeago: takes a timestamp, figures out how long ago it was
def timeago(timestamp):
    hoursago = (time.time() - timestamp)/60/60
    if hoursago < 24:
        return 'today'
    elif hoursago < 24*2:
        return 'yesterday'
    elif hoursago < 24*7:
        return 'this week'
    elif hoursago < 24*30:
        return 'this month'
    elif hoursago < 24*30*2:
        return 'last month'
    else:
        return '%i months ago' % int(hoursago/24/30)

# xapianrunquery: runs a query against the db
def xapianrunquery(cur, dbs, query, limit=maxresults):
    # split the query into words
    querysplit = query.split()
    # startterms: everything except the last word
    startterms = querysplit[:-1]
    # endterms: all known words that start like startterms
    endterms = [x.term for x in dbs.allterms(querysplit[-1])]
    if startterms != [] and len(endterms) > 1:
        buildquery = string.join(startterms, ' AND ') + ' AND (' + string.join(endterms, ' OR ') + ')'
    elif startterms == [] and len(endterms) > 1:
        buildquery = string.join(endterms, ' OR ')
    elif startterms != [] and len(endterms) == 1:
        buildquery = string.join(startterms + endterms, ' AND ')
    elif startterms == [] and len(endterms) == 1:
        buildquery = string.join(endterms)
    else:
        buildquery = string.join(querysplit, ' AND ')
    enquire = xapian.Enquire(dbs)
    queryparser = xapian.QueryParser()
    queryhandle = queryparser.parse_query(buildquery)
    enquire.set_query(queryhandle)
    matches = enquire.get_mset(0,limit)

    results = []

    for i in matches:
        doc = i.get_document()
        pagedata = dipdatabase(cur, doc.get_data())
        results.append(pagedata)

    return results

# pgrunquery: run the query against the postgresql db, checking the access
#             control lists to only display public pages.
def pgrunquery(cur, query, limit=maxresults):
    # append % to the query -- we have to do this here, because we use
    # query parameters in the query
    query = query.lower() + '%'
    wikicomm = 'wiki community/' + query.lower() + '%'
    cur.execute("""
        SELECT propercased_name,edittime
        FROM curpages
            LEFT JOIN
            (
                SELECT pagename, may_read AS has_read_priv
                FROM pageacls
                WHERE groupname IN ('All')
            )
            AS access
            ON (access.pagename = curpages.name)
        WHERE (name like %(query)s OR name like %(wikicomm)s)
              AND text not ilike '#redirect %%'
              AND name not like '%%/comments'
              AND (has_read_priv IS NULL OR has_read_priv)
        ORDER BY propercased_name
    """, dict(query=query, wikicomm=wikicomm))
    return cur.fetchall()

# dipdatabase: gets propercased_name and edittime
def dipdatabase(cur, name):
    result = mc.get(memcachedtag + 'pcet-' + urllib.quote(name))
    if not result:
        cur.execute("SELECT propercased_name,edittime FROM curpages WHERE name = %(name)s", dict(name=name))
        result = cur.fetchone()
        if result:
            mc.set(memcachedtag + 'pcet-' + urllib.quote(name), result, time=43200)
    return result

# Open a database cursor
try:
    conn = psycopg2.connect(database=config.db_name, user=config.db_user, password=config.db_user_password)
except:
    sys.stdout.write("Content-type: text/plain\n\n")
    sys.exit(0)

cur = conn.cursor()

# Prep xapian
#dbs = xapian.Database()
#for i in databases:
#    dbs.add_database(xapian.Database(i))

mc = memcache.Client(config.memcache_servers)

skipall = False

# Read the query parameter
form = cgi.FieldStorage()
if not (form.has_key("format")): format = 'json'
else: format = form["format"].value
if not (form.has_key("query")): query = 'Front Page'
else: query = urllib.unquote_plus(form["query"].value)
if (form.has_key("search")):
    # This is coming in from ajaxSuggestions.js
    format = 'list'
    query = urllib.unquote_plus(form["search"].value)

# Process the request
# Gets propercased_name (human-readable name), edittime (unix timestamp)
rows = mc.get(memcachedtag + urllib.quote(query))

if not rows:
    #rows = xapianrunquery(cur, dbs, query)
    rows = pgrunquery(cur, query)

    if len(rows) == 0:
        # try just the plain name
        result = dipdatabase(cur, query)
        if result: rows = [result]
    
    if len(rows) > 0:
        mc.set(memcachedtag + urllib.quote(query), rows, time=86400)

if format == 'json':
    # Create a better array with better stuff
    resultlist = []
    desclist = []
    urllist = []
    for i in rows:
        pagename = i[0]
        description = 'edited ' + timeago(i[1])
        url = 'http://%s/%s' % (config.wiki_base_domain, pagename.replace(' ','_'))
        resultlist.append(pagename)
        desclist.append(description)
        urllist.append(url)

    sys.stdout.write('Content-type: application/json\n\n')
    sys.stdout.write(json.dumps([query, resultlist, desclist, urllist]))

elif format == 'jsonsimple':
    # Create a list of just page names
    resultlist = []
    for i in rows:
        resultlist.append(i[0])

    sys.stdout.write('Content-type: application/json\n\n')
    sys.stdout.write(json.dumps(resultlist))

elif format == 'list':
    sys.stdout.write('Content-type: text/html\n\n')
    sys.stdout.write('<ul>')
    tabindex = 1
    for i in rows:
        output = {}
        output['tabindex'] = tabindex
        tabindex += 1
        if len(i[0]) < 30:
            output['pagename'] = i[0]
            output['description'] = 'edited ' + timeago(i[1])
        else:
            output['pagename'] = i[0][:30] + '...'
            output['description'] = i[0] + ', edited ' + timeago(i[1])
        output['url'] = 'http://%s/%s' % (config.wiki_base_domain, i[0].replace(' ','_'))
        if time.time()-i[1] < 24*60*60:
            if len(i[0]) < 23:
                tempname = i[0]
            else:
                tempname = i[0][:23] + '...'
            output['pagename'] = tempname + ' <img src="http://%s/wiki/%s/img/sycamore-updated.png" width="59" height="13" alt="[UPDATED]" title="Last updated today!">' % (config.wiki_base_domain, config.theme_default)
        sys.stdout.write('<li><a tabindex="%(tabindex)i" href="%(url)s" class="item" title="%(description)s">%(pagename)s</a></li>' % output)
    sys.stdout.write('</ul><p>')
    if len(rows) >= maxresults:
        sys.stdout.write('More results available!')
    sys.stdout.write('<a href="?action=search&inline_string=%(quotedquery)s"><b>Search</b> for <i>%(query)s</i>...</a></p>' % dict(quotedquery=urllib.quote_plus(query), query=query))
else:
    sys.stdout.write('Content-type: text/plain\n\nUnknown format: %s\n' % format)

