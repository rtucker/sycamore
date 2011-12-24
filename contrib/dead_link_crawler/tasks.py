from celery.task import task
from celery.task.sets import subtask, TaskSet
from StringIO import StringIO
from xml.etree.ElementTree import ElementTree

import bz2
import dateutil.parser
import memcache
import os
import pycurl
import random
import re
import robotparser
import sqlite3
import time
import urllib
import urlparse

MEMCACHE = ['127.0.0.1:11211']
VERSION = "2011122404"
USERAGENT = "sycamore_dead_link_crawler/%s (http://rocwiki.org/)" % VERSION
GAP = 30

@task
def slugify(value):
    "Turn a string into a clean, sluggy string.  Thanks to Django."
    import unicodedata
    value = unicodedata.normalize('NFKD', unicode(value)).encode('ascii', 'ignore')
    value = unicode(re.sub('[^\w\s-]', '', value).strip().lower())
    value = unicode(re.sub('[-\s]+', '-', value))
    return value

@task
def fetch_url(url, referer=None, headonly=False, callback=None):
    "Retrieves a given URL, calling back a tuple of strings (body, header)"
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
    c.setopt(pycurl.CONNECTTIMEOUT, 60)
    c.setopt(pycurl.TIMEOUT, 240)
    c.perform()
    b.seek(0)
    h.seek(0)
    if callback is not None:
        subtask(callback).delay((b.read(), h.read()))
    return (b.read(), h.read())

@task
def decompress(content, extension='bz2', callback=None):
    "Decompresses a string.  Currently only does bzip2."
    if extension == 'bz2':
        decompress.update_state(state="UNBZIP2")
        out = bz2.decompress(content)
    else:
        out = content
    if callback is not None:
        subtask(callback).delay(out)
    return out

@task
def parse_pages(text, callback=None):
    """
    Given an XML document string, returns a list of pageinfo dicts.
    Calls back on each page if callback is set.
    """
    namespace = "{http://www.mediawiki.org/xml/export-0.4/}"

    fd = StringIO()
    fd.write(text)
    fd.seek(0)

    tree = ElementTree(file=fd)
    root = tree.getroot()

    siteinfo = root.find('%ssiteinfo' % namespace)
    sitebase = siteinfo.find('%sbase' % namespace).text

    if not root.tag == '%smediawiki' % namespace:
        raise ValueError("This does not appear to be a MediaWiki-style XML dump: %s" % root.tag)

    result = []

    for page in root.getiterator(tag='%spage' % namespace):
        if len(result) % 100 == 0:
            parse_pages.update_state(state="PARSING", meta={'pages': len(result)})

        page_title = page.find('%stitle' % namespace).text.encode("ascii", "xmlcharrefreplace")
        page_timestamp = dateutil.parser.parse('1970-01-01T00:00:00Z')
        page_url = urllib.basejoin(sitebase, urllib.quote(page_title.replace(' ', '_')).decode('utf-8'))
        text = None
        for revision in page.getiterator(tag='%srevision' % namespace):
            rev_timestamp = revision.find('%stimestamp' % namespace).text
            rev_timestamp = dateutil.parser.parse(rev_timestamp)
            if rev_timestamp > page_timestamp:
                page_timestamp = rev_timestamp
                text = revision.find('%stext' % namespace).text

        page_ts = time.mktime(page_timestamp.timetuple())

        pageinfo = {
            'title':        page_title,
            'timestamp':    page_ts,
            'url':          page_url,
            'text':         text,
        }

        if callback is not None:
            subtask(callback).delay(pageinfo)
        result.append(pageinfo)

    return result

@task
def pluck_links_from_text(text, callback=None):
    """
    Given a string, returns a list of linkinfo dicts.
    Calls back on each link if callback is set.
    """
    result = []
    for candidate in re.finditer("\[[^]]*\]", text):
        if candidate.group().startswith('[http'):
            # we have a link!
            bunch = candidate.group().strip('[]').split(' ', 1)
            link_url = bunch[0]
            if len(bunch) == 1:
                link_text = ''
            else:
                link_text = bunch[1]

            linkinfo = {
                'url': link_url,
                'text': link_text,
            }

            if callback is not None:
                subtask(callback).delay(linkinfo)
            result.append(linkinfo)

    return result

@task
def parse_links(pageinfo, callback=None):
    """
    Given a pageinfo, returns a list of linkinfo dicts.
    If callback is set, calls back on each link.

    Convenience wrapper for pluck_links_from_text.
    """
    links = pluck_links_from_text(pageinfo['text'])
    if callback is not None:
        for link in links:
            subtask(callback).delay(link)
    return links

@task
def test_validity(body, headers, url, referer=None, callback=None):
    """
    Tests a URL for validity.  Returns a tuple of:
        (url, true or false, status)
    Considers anything other than a 200 to be invalid.
    """
    try:
        http, status = headers.split('\n')[0].split(' ', 1)
        if not status.startswith('200'):
            result = (url, False, status)
        else:
            result = (url, True, status)
    except pycurl.error as err:
        result = (url, False, str(err))

    if callback is not None:
        subtask(callback).delay(result)
    return result

@task
def check_robot_ok(url, callback=None):
    """
    Checks to see if we can crawl the url in question.
    """
    urlp = urlparse.urlparse(url)

    if MEMCACHE:
        mc = memcache.Client(MEMCACHE)
        keyname = __name__ + '_robotstxt_' + urlp.netloc
        keyname = keyname.encode('ascii', 'ignore')
        robotstxt = mc.get(keyname)
    else:
        # Ensure our database is set up correctly.
        conn = sqlite3.connect('cache.sqlite')
        c = conn.cursor()
        c.execute(u'pragma table_info(robotscache)')
        columns = ' '.join(i[1] for i in c.fetchall()).split()
        if columns == []:
            c.execute(u"""create table robotscache
                (domain text, robotstxt text, lastcheck integer)""")
            conn.commit()

        # Check our database cache.
        c.execute(u'select robotstxt from robotscache where domain = ? and lastcheck > ? order by lastcheck desc',
                  (urlp.netloc.lower(), time.time()-86400,))
        out = c.fetchone()
        if out:
            # We already have a robots.txt on file.
            robotstxt = out[0]
        else:
            robotstxt = None

    if not robotstxt: 
        # No robots.txt on file within the past 24 hours; get one.
        url = urlparse.urljoin(urlp.scheme + '://' + urlp.netloc, 'robots.txt')
        robotstxt, headers = fetch_url(url)

        if MEMCACHE:
            mc.set(keyname, robotstxt, time=time.time()+86400)
        else:
            c.execute(u'delete from robotscache where domain = ? and lastcheck < ?',
                      (urlp.netloc.lower(), time.time(),))
            c.execute(u'insert into robotscache (domain, robotstxt, lastcheck) values (?, ?, ?)',
                      (urlp.netloc.lower(), robotstxt.decode('utf-8'), time.time(),))
            conn.commit()
            # Done with database.  Close the file before we go any further.
            conn.close()

    # Use robotparser to evaluate the situation.
    rp = robotparser.RobotFileParser()
    rp.parse(robotstxt)
    result = rp.can_fetch(USERAGENT, url)

    if callback is not None:
        subtask(callback).delay(result)
    return result

@task
def next_hit_in(domain, gap=GAP, callback=None):
    """
    Gives the number of seconds until the next time we can hit a given domain.
    Returns '0' if we haven't hit it in [gap] seconds.
    """
    if domain == 'rocwiki.org':
        # We know we can handle the traffic.  :-)
        gap = 1

    if MEMCACHE:
        mc = memcache.Client(MEMCACHE)
        keyname = __name__ + '_hittime_' + domain
        keyname = keyname.encode('ascii', 'ignore')
        result = 0
        now = int(time.time())
        last_hit = mc.get(keyname)

        if last_hit:
            result = gap - int(time.time()-last_hit)

        if result < 1:
            result = 0
            mc.set(keyname, now, time=now+gap)

    else:
        # Ensure database is set up correctly.
        conn = sqlite3.connect('cache.sqlite')
        c = conn.cursor()
        c.execute(u'pragma table_info(hitcache)')
        columns = ' '.join(i[1] for i in c.fetchall()).split()
        if columns == []:
            c.execute(u"""create table hitcache
                (domain text, lasthit integer)""")
            conn.commit()

        # Check our database-cache for last hit information.
        c.execute(u'select lasthit from hitcache where domain = ? and lasthit > ?', (domain.lower(), time.time()-gap))
        out = c.fetchone()
        if out:
            # We have hit the domain lately.  We're going to have to wait.
            result = gap - int(time.time()-out[0])
        else:
            # We haven't hit the domain lately.  Purge old rows and add a new one,
            # assuming we're going to hit the domain now.
            c.execute(u'delete from hitcache where domain = ?', (domain.lower(),))
            c.execute(u'insert into hitcache (domain, lasthit) values (?,?)', (domain.lower(), time.time()))
            conn.commit()
            result = 0

        # Close database.
        conn.close()

    if callback is not None:
        subtask(callback).delay(result)
    return result

@task(acks_late=True)
def test_link(pageinfo, linkinfo, callback=None):
    """
    Given a pageinfo and linkinfo, tests the link for validity.
    """
    logger = test_link.get_logger()
    urlp = urlparse.urlparse(linkinfo['url'])
    nexttime = next_hit_in(urlp.netloc)
    if nexttime > 0:
        # Time to sit on our horses for a bit.
        delay = random.randint(nexttime, nexttime+GAP)
        logger.warning("%s: %s: rate limiting on domain, retry in %i" % (pageinfo['title'], linkinfo['url'], delay,))
        test_link.retry(countdown=delay, max_retries=100)

    # Ensure the server allows our lowly robot to connect.
    test_link.update_state(state="ROBOTCHECK")
    try:
        robotok = check_robot_ok(linkinfo['url'])
    except Exception, exc:
        logger.warning("%s: %s: robots.txt could not be accessed (%s)" % (pageinfo['title'], linkinfo['url'], exc))
        robotok = True

    if not robotok:
        logger.warning("%s: %s: robots.txt prohibits" % (pageinfo['title'], linkinfo['url']))
        resbool = True   # de-facto good
        resstatus = 'robots.txt prohibits'
    else:
        try:
            # Test the URL.
            test_link.update_state(state="FETCHURL")
            body, headers = fetch_url(linkinfo['url'], referer=pageinfo['url'])
            resurl, resbool, resstatus = test_validity(body, headers, linkinfo['url'])
        except Exception, exc:
            logger.warning("%s: %s: page could not be accessed (%s)" % (pageinfo['title'], linkinfo['url'], exc))
            resurl = linkinfo['url']
            resbool = False
            resstatus = ('Exception: %s' % exc)

        logger.info("%s: %s: is %s" % (pageinfo['title'], linkinfo['url'], 'valid' if resbool else 'not valid'))

    result = {
        'pageinfo': pageinfo,
        'linkinfo': linkinfo,
        'valid': resbool,
        'status': resstatus,
    }

    if callback is not None:
        subtask(callback).delay(result)
    return result

@task
def build_tasklist_for_page(pageinfo, callback=None):
    """
    Given a pageinfo, returns a list of test_link.subtasks.
    Useful for building a TaskSet or chord.
    """
    result = []

    for linkinfo in parse_links(pageinfo):
        result.append(test_link.subtask((pageinfo, linkinfo)))

    if callback is not None:
        subtask(callback).delay(result)

    return result

@task
def create_table_for_page(results, pageinfo, callback=None):
    """
    Given a list of results and a pageinfo, returns a string of wikimarkup
    for a table row.
    """
    result = []
    if type(results) is not list:
        results = [results]

    for r in results:
        if not r['valid']:
            boxcolor = 'BFBAAB' if r['status'].startswith('3') else 'A68E47'
            if len(r['linkinfo']['url']) > 50:
                dispurl = r['linkinfo']['url'][0:40] + '...' + r['linkinfo']['url'][-10:]
            else:
                dispurl = r['linkinfo']['url']
            result.append('||<#%s>[%s %s] (%s)||\n' % (
                boxcolor, r['linkinfo']['url'], dispurl,
                r['status'].strip(),))

    if len(result) < 3:
        rowcolor = 'EEEEFF'
    elif len(result) < 6:
        rowcolor = 'E8E8FF'
    else:
        rowcolor = 'AEAEBF'

    if len(result) > 0:
        result.insert(0, '||<|%i #%s>["%s"]||\n' % (
            len(result)+1, rowcolor, pageinfo['title'],))

    result = ''.join(result)

    if callback is not None:
        subtask(callback).delay(result)
    return result

@task
def write_string_to_file(string, filename):
    """
    Our output function.  Writes a string to a hashed directory tree.
    """
    logger = write_string_to_file.get_logger()

    if string == '':
        # No need to bother.
        return

    try:
        filename = slugify(filename)

        # Create hashed directories.
        try:
            os.mkdir('out/', 0755)
        except OSError:
            pass

        try:
            os.mkdir('out/%s/' % filename[0].upper(), 0755)
        except OSError:
            pass

        # Write to the file!
        fd = open('out/%s/%s' % (filename[0].upper(), filename,), 'w')
        fd.write(string)
        fd.close()
    except Exception, exc:
        logger.error("Bombed out trying to write %s: %s" % (filename, exc))
        write_string_to_file.retry(exc=exc)
