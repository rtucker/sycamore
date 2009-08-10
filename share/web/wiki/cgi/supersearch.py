#!/usr/bin/python

# Returns ALL pages that match a string

# Ryan Tucker <rtucker@gmail.com>, November 27 2008

maxresults = 1000

# Imports
import cgi
import cgitb; cgitb.enable(display=0, logdir="/tmp")
import psycopg2
import sys
import time
import urllib

# Where am I?  Split argv[0] on /share and add the first half to the path.
sycamoreroot = sys.argv[0].split('/share')[0]
sys.path.append(sycamoreroot)
# Now import some stuff from Sycamore...
from Sycamore import config

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

# runquery: runs a query against the db
def runquery(cur, query, limit=maxresults):
    cur.execute("SELECT propercased_name,edittime FROM curpages WHERE text ilike %(query)s ORDER BY edittime LIMIT %(limit)s", dict(query='%%' + query + '%%', limit=limit))
    return cur.fetchall()

# Open a database cursor
try:
    conn = psycopg2.connect(database=config.db_name, user=config.db_user, password=config.db_user_password)
except:
    sys.exit(0)

cur = conn.cursor()

# Read the query parameter
form = cgi.FieldStorage()
if not (form.has_key("query")): query = ''
else: query = urllib.unquote_plus(form["query"].value)

# Process the request
# Gets propercased_name (human-readable name), edittime (unix timestamp)
sys.stdout.write('Content-type: text/html\n\n')
sys.stdout.write('<html><head><title>Sycamore SuperSearch</title></head><body><p>Sycamore SuperSearch</p>')
sys.stdout.write('<form method="GET"><input name="query" value="%(query)s" size="40"><input type="submit"></form>' % dict(query=query))

if query:
    rows = runquery(cur, query)

    sys.stdout.write('<p>SuperSearch for %(query)s: %(len)s results</p><ul>' % dict(query=query, len=len(rows)))
    for i in rows:
        output = {}
        if len(i[0]) < 30:
            output['pagename'] = i[0]
            output['description'] = 'edited ' + timeago(i[1])
        else:
            output['pagename'] = i[0][:30] + '...'
            output['description'] = i[0] + ', edited ' + timeago(i[1])
        output['url'] = 'http://%s/%s' % (config.wiki_base_domain, i[0].replace(' ','_'))
        output['edit'] = output['url'] + '?action=edit'
        if time.time()-i[1] < 24*60*60:
            if len(i[0]) < 23:
                tempname = i[0]
            else:
                tempname = i[0][:23] + '...'
            output['pagename'] = tempname + ' <img src="http://%s/wiki/%s/img/sycamore-updated.png" width="59" height="13" alt="[UPDATED]" title="Last updated today!">' % (config.wiki_base_domain, config.theme_default)
        sys.stdout.write('<li>[<a href="%(edit)s" target="_blank">edit</a>] <a href="%(url)s" class="item" title="%(description)s">%(pagename)s</a></li>' % output)
    sys.stdout.write('</ul>')

