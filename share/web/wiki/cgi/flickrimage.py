#!/usr/bin/python

# A CGI that returns an image from Flickr.  Works best with Sycamore's
# Flickr macro.

# Requres the following to be set in Sycamore's config:
#  flickr_apikey, flickr_apisecret

# Ryan Tucker <rtucker@gmail.com> for Project Sycamore

import cgi
import cgitb; cgitb.enable(display=0, logdir="/tmp")
import os
import sys
import time
import urllib

# Where am I?  Split argv[0] on /share and add the first half to the path.
sycamoreroot = sys.argv[0].split('/share')[0]
sys.path.append(sycamoreroot)
# Now import some stuff from Sycamore...
from Sycamore import config
from Sycamore.support import flickr
from Sycamore.support import memcache

if config.memcache and config.flickr_apikey and config.flickr_apisecret:
    mc = memcache.Client(config.memcache_servers)
    flickr.API_KEY = config.flickr_apikey
    flickr.API_SECRET = config.flickr_apisecret
else:
    sys.stdout.write('Content-type: text/plain\n\n')
    sys.stdout.write('Please configure memcache, flickr_apikey, and flickr_apisecret.\n')
    
cachedimage = cachedok = cachedurls = True

form = cgi.FieldStorage()
if form.has_key("id"):
    photoid = form["id"].value
else:
    raise KeyError
if form.has_key("size"):
    size = form["size"].value.capitalize()
else:
    size = 'Small'

photo = flickr.Photo(id=photoid)
mctag = 'flickr-%s-%s-' % (photoid, size)

# crawl licenses
oklicenses = ['1','2','3','4','5','6','7']
ok = mc.get(mctag + 'ok')
if not ok:
    if (photo.license in oklicenses) and (photo.ispublic):
        ok = True
        mc.set(mctag + 'ok', time=60*60*12, val=ok)
        cachedok = False
    else:
        ok = False

if ok:
    # grab urls
    urls = mc.get(mctag + 'urls')
    if not urls:
        urls = {}
        urls['img'] = photo.getURL(urlType='source',size=size)
        urls['link'] = photo.getURL(urlType='url',size=size)
        mc.set(mctag + 'urls', time=60*60*24, val=urls)
        cachedurls = False

    # grab photo
    image = mc.get(mctag + 'img')
    if not image:
        urlinstance = urllib.URLopener()
        fd = urlinstance.open(urls['img'])
        image = fd.read()
        mc.set(mctag + 'img', time=60*60*24*3, val=image)
        cachedimage = False

    sys.stdout.write('Content-Type: image/jpeg\n')
    sys.stdout.write('Content-Length: %i\n' % len(image))
    sys.stdout.write('Expires: ' + time.strftime('%a, %d %b %Y %H:%M:%S GMT', time.gmtime(time.time()+7*24*60*60)) + '\n')
    sys.stdout.write('\n')
    sys.stdout.write(image)
else:
    sys.stdout.write('Content-type: text/plain\n\n')
    sys.stdout.write('license fail!\n')
    sys.stdout.write('cachedimage: %(cachedimage)s, cachedok: %(cachedok)s, cachedurls: %(cachedurls)s\n' % dict(cachedimage=cachedimage, cachedok=cachedok, cachedurls=cachedurls))

