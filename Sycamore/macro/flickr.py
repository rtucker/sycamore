# -*- coding: utf-8 -*-
"""
  [[Flickr(photo id, caption, size, alignment, thumb, noborder)]]

  photo id : flickr id number for the photo (the last big number in the URL)
    required. should provide error message if not present.
    must be the first element. all others can be in any order.

  size : the size of the image, as expected by flickr.  This will be
    something like Square, Thumbnail, Small, Medium, Large, Original, etc.

  alignment : left/right. if it's a thumbnail then it gives it a usual
    float:left or float:right. if it's not a thumbnail then you need to wrap
    the image in a span that sends it left or right (i'm not sure it even
    needs to float..)

  thumb : this is just the string "thumb" or "thumbnail" that tells us it's
    a thumbnail. optional if size is supplied, if size not supplied defaults
    to Small. Should default size be a systemwide variable, or hard
    coded?

  noborder : just the string "noborder" to tell us, for non-thumbnails, to not
    use the tiny black image border. in the case it's a thumbnail, i suppose
    the best behavior would be to drop the caption and frame around the
    thumbnail (sort of consealing its thumbnail-ness)
    (We can have a caption w/o a border, as well)

This module requires that flickr_cgiurl be pointing at a working copy of
share/web/wiki/cgi/flickrimage.py and that its requirements be met.
"""

Dependencies = []

from Sycamore import config
from Sycamore.support import flickr
from Sycamore import wikidb
from Sycamore import wikiutil
import re
import sys
import string
import urllib

IMAGE_MACRO = re.compile(r'^(\s*(\[\[flickr((\(.*\))|())\]\])\s*)+$')

flickr.API_KEY = config.flickr_apikey
flickr.API_SECRET = config.flickr_apisecret

def recordCaption(pagename, linked_from_pagename, image_name, caption, request):
    """
    records the caption to the db so that we can easily look it up

    very simple -- no versioning or anything.
    just keeps it there for easy/quick reference
    (linked_from_pagename is for future use)
    """
    cursor = request.cursor
    mydict = {'pagename': pagename.lower(), 'image_name': image_name,
              'caption': caption, 'linked_from_pagename': linked_from_pagename,
              'wiki_id': request.config.wiki_id}
    cursor.execute("""SELECT image_name
                      FROM imageCaptions
                      WHERE attached_to_pagename=%(pagename)s and
                            image_name=%(image_name)s and
                            linked_from_pagename=%(linked_from_pagename)s and
                            wiki_id=%(wiki_id)s""", mydict)
    result = cursor.fetchone()
    if result:
        cursor.execute("""
            UPDATE imageCaptions
            SET caption=%(caption)s
            WHERE attached_to_pagename=%(pagename)s and
                  image_name=%(image_name)s and
                  linked_from_pagename=%(linked_from_pagename)s and
                  wiki_id=%(wiki_id)s""", mydict)
    else:
        cursor.execute("""INSERT INTO imageCaptions
                          (attached_to_pagename, image_name, caption,
                           linked_from_pagename, wiki_id)
                          values (%(pagename)s, %(image_name)s, %(caption)s,
                                  %(linked_from_pagename)s, %(wiki_id)s)""",
                       mydict)

def deleteCaption(pagename, linked_from_pagename, image_name, request):
    request.cursor.execute("""
        DELETE FROM imageCaptions
        WHERE attached_to_pagename=%(pagename)s and
              image_name=%(image_name)s and
              linked_from_pagename=%(linked_from_pagename)s and
              wiki_id=%(wiki_id)s""",
        {'pagename':pagename.lower(), 'image_name':image_name,
         'linked_from_pagename':linked_from_pagename,
         'wiki_id':request.config.wiki_id})

def getImageSize(pagename, photohandle, size, request):
    """ returns width vs. height for image """
    sizedata = request.mc.get('flickr-%s-%s-sizedata' % (photohandle.id.encode(config.charset), size))
    if not sizedata:
        sizedata = photohandle.getSizes()
        request.mc.set('flickr-%s-%s-sizedata' % (photohandle.id.encode(config.charset), size), sizedata, time=3*24*60*60)
    for i in sizedata:
        if i['label'].lower() == size.lower():
            return (i['width'], i['height'])

def touchCaption(pagename, linked_from_pagename, image_name, caption, request):
    stale = True
    db_caption = ''
    cursor = request.cursor
    cursor.execute("""SELECT caption
                      FROM imageCaptions
                      WHERE attached_to_pagename=%(pagename)s and
                            linked_from_pagename=%(linked_from_pagename)s and
                            image_name=%(image_name)s and
                            wiki_id=%(wiki_id)s""",
                   {'pagename':pagename.lower(),
                    'linked_from_pagename':linked_from_pagename,
                    'image_name':image_name,
                    'wiki_id':request.config.wiki_id})
    result = cursor.fetchone()
    if result:
        db_caption = result[0]
    if caption != db_caption:
        recordCaption(pagename, linked_from_pagename, image_name, caption,
                      request)
    if not caption:
        deleteCaption(pagename, linked_from_pagename, image_name, request)

def getArguments(args):
    """
    This gets the arguments given to the image macro.

    This function is gross and should be redone by a regular expression,
    but only if it's somehow less gross.
    """
    #filename stuff
    split_args = args.split(',')
    f_end_loc = len(split_args[0])

    caption = ''
    px_size = 'Small'
    alignment = ''
    thumbnail = False
    border = True

    # mark the beginning of the non-filename arguments
    # we use this to figure out what the image name is if there are commas
    # in the image name
    start_other_args_loc = len(args)

    # gross, but let's find the caption, if it's there
    q_start = args.find('"')
    q_end = 0
    if q_start != -1:
        # we have a quote
        q_end = q_start
        quote_loc = args[q_end+1:].find('"')
        q_end += quote_loc + 1
        while quote_loc != -1:
            quote_loc = args[q_end+1:].find('"')
            q_end += quote_loc + 1
        caption = args[q_start+1:q_end]
        # mark the start of the caption so that we can use it to grab the
        # image name if we need to
        start_other_args_loc = min(start_other_args_loc, q_start-1)
    else:
      q_start = 0

    # let's get the arguments without the caption or filename
    if caption:
        simplier_args = args[f_end_loc+1:q_start] + args[q_end+1:]
        # now our split will work to actually split properly
        list_args = simplier_args.split(',')
    else:
        list_args = args.split(',')[1:]

    arg_loc = len(args.split(',')[0])
    for arg in list_args:
        clean_arg = arg.strip().lower()
        if clean_arg.startswith('thumb'):
            thumbnail = True
        elif clean_arg == 'noborder':
            border = False
        elif clean_arg == 'left':
            alignment = 'left'
        elif clean_arg == 'right':
            alignment = 'right'
        elif (clean_arg in ["small", "medium", "large", "original"]):
            px_size = arg.strip().capitalize().encode()
        else:
            # keep track of how far we've gone
            arg_loc += len(arg) + 1
            continue

        # keep track of how far we've gone
        start_other_args_loc = min(start_other_args_loc, arg_loc)
        arg_loc += len(arg) + 1

    # image name is the distance from the start of the string to the
    # first 'real' non-filename argument
    image_name = args[:start_other_args_loc].strip()
    # there may be leftover commas
    end_char = image_name[-1]
    while end_char == ',':
        image_name = image_name[:-1]
        end_char = image_name[-1]

    return (image_name, caption.strip(), thumbnail, px_size, alignment, border)

def line_has_just_macro(macro, args, formatter):
    line = macro.parser.lines[macro.parser.lineno-1].lower().strip()
    if IMAGE_MACRO.match(line):
        return True
    return False

def licenses_getInfo(license_id):
    """Returns (name, url) for a license given its license_id"""
    method = 'flickr.photos.licenses.getInfo'
    data = flickr._doget(method, auth=False)
    license_id = int(license_id)

    if license_id in [1, 2, 3, 4, 5, 6]:
        license_class = 'Creative Commons 2.0 '
    else:
        license_class = ''

    try:
        name = 'License: ' + license_class + data.rsp.licenses.license[license_id].name
        url = data.rsp.licenses.license[license_id].url
        return (name, url)
    except:
        return None

def execute(macro, args, formatter=None):
    if not formatter:
        formatter = macro.formatter
    if line_has_just_macro(macro, args, formatter):
      macro.parser.inhibit_br = 2

    if config.memcache:
        mc = macro.request.mc
    else:
        return formatter.rawHTML('<!-- Flickr support requires memcache -->')

    macro_text = ''

    baseurl = config.flickr_cgiurl
    html = []
    pagename = formatter.page.page_name
    urlpagename = wikiutil.quoteWikiname(formatter.page.proper_name())

    if not args:
        macro_text += formatter.rawHTML(
            '<b>Please supply at least an image ID, e.g. '
            '[[Flickr(3046120549)]], where 3046120549 is a Flickr '
            'photo ID number.</b>')
        return macro_text

    # id, "caption, here, yes", Large, right --- in any order
    # (filename first)
    # the 'Large' is the size

    # parse the arguments
    try:
        (image_name, caption, thumbnail, px_size, alignment,
         border) = getArguments(args)
    except:
        macro_text += formatter.rawHTML('[[Flickr(%s)]]' % wikiutil.escape(args))
        return macro_text

    url_image_name = urllib.quote(image_name.encode(config.charset))

    photohandle = flickr.Photo(image_name)
    try:
        validsizes = mc.get('flickr-%s-validsizes' % url_image_name)
        if not validsizes:
            validsizes = []
            for i in photohandle.getSizes():
                validsizes.append(i['label'].lower())
                mc.set('flickr-%s-validsizes' % url_image_name, validsizes, time=3*24*60*60)
    except flickr.FlickrError:
        macro_text += '%s does not seem to be a valid Flickr photo' % image_name
        return macro_text

    licensename = mc.get('flickr-license-%s' % photohandle.license)
    try:
        # sanity check on licensename
        tmpfoo1, tmpfoo2 = licensename
        if not (type(tmpfoo1) == type(tmpfoo2) == type(str())):
            licensename = None
    except:
        licensename = None

    if not licensename:
        licensename = licenses_getInfo(photohandle.license)
        if licensename:
            mc.set('flickr-license-%s' % photohandle.license, licensename, time=3*24*60*60)
        else:
            licensename = ('unknown license id %s', 'http://www.flickr.com/services/api/flickr.photos.licenses.getInfo.html')
            mc.set('flickr-license-%s' % photohandle.license, licensename, time=60*60)

    size = px_size
    oklicenses = ['1','2','3','4','5','6','7','8']
    ok = mc.get('flickr-%s-%s-ok' % (url_image_name, size))

    if not ok:
        if (photohandle.license in oklicenses) and (photohandle.ispublic):
            ok = True
            mc.set('flickr-%s-%s-ok' % (url_image_name, size), ok, time=60*60*12)
        else:
            ok = False

    if not ok:
        macro_text += 'License for image %s does not allow us to include this image.' % image_name
        return macro_text
    if px_size.lower() not in validsizes:
        macro_text += '%s is not a valid size for %s.  Try: %s' % (px_size, image_name, string.join(validsizes, ', '))
        return macro_text

    ownername = mc.get('flickr-%s-owner' % (url_image_name))
    if not ownername:
        ownername = photohandle.owner.username
        mc.set('flickr-%s-owner' % (url_image_name), ownername)

    if not ownername: ownername = '(unknown)'

    if (macro.formatter.processed_thumbnails.has_key(
            (pagename, image_name)) and
        (thumbnail or caption)):
        macro_text += ('<em style="background-color: #ffffaa; padding: 2px;">'
                       'A thumbnail or caption may be displayed only once per '
                       'image.</em>')
        return macro_text

    macro.formatter.processed_thumbnails[(pagename, image_name)] = True

    urls = mc.get('flickr-%s-%s-urls' % (url_image_name, size))
    if not urls:
        urls = {}
        urls['img'] = photohandle.getURL(urlType='source',size=size)
        urls['link'] = photohandle.getURL(urlType='url',size=size)
        mc.set('flickr-%s-%s-urls' % (url_image_name, size), urls, time=60*60*24)

    full_size_url = urls['link']

    # put the caption in the db if it's new and if we're not in preview mode
    if not formatter.isPreview():
        touchCaption(pagename, pagename, image_name, caption, macro.request)
    if caption:
        caption += ' (by Flickr user %s [%s license info])' % (ownername, licensename[1])
        # parse the caption string
        caption = wikiutil.stripOuterParagraph(wikiutil.wikifyString(
            caption, formatter.request, formatter.page, formatter=formatter))

    if thumbnail:
        # let's generated the thumbnail or get the dimensions if it's
        # already been generated
        if not px_size:
            px_size = default_px_size
        x, y = getImageSize(pagename, photohandle, px_size, macro.request)
        d = {'right':'floatRight', 'left':'floatLeft', '':'noFloat'}
        floatSide = d[alignment]
        if caption and border:
            html.append('<span class="%s thumb" style="width: %spx;">'
                        '<a style="color: black;" href="%s">'
                        '<img src="%s" alt="%s" title="%s" style="display:block;"/></a>'
                        '<span>%s</span>'
                        '</span>' %
                        (floatSide, int(x)+2, full_size_url,
             baseurl + '?id=' + image_name + '&size=' + px_size,
                         image_name, licensename[0], caption))
        elif border:
            html.append('<span class="%s thumb" style="width: %spx;">'
                        '<a style="color: black;" href="%s">'
                        '<img src="%s" alt="%s" title="%s" style="display:block;"/></a>'
                        '</span>' %
                        (floatSide, int(x)+2, full_size_url,
             baseurl + '?id=' + image_name + '&size=' + px_size,
                         image_name, licensename[0]))
        elif caption and not border:
            html.append('<span class="%s thumb noborder" style="width: %spx;">'
                        '<a style="color: black;" href="%s">'
                        '<img src="%s" alt="%s" title="%s" style="display:block;"/></a>'
                        '<span>%s</span></span>' %
                        (floatSide, int(x)+2, full_size_url,
             baseurl + '?id=' + image_name + '&size=' + px_size,
                         image_name, licensename[0], caption))
        else:
            html.append('<span class="%s thumb noborder" style="width: %spx;">'
                        '<a style="color: black;" href="%s">'
                        '<img src="%s" alt="%s" title="%s" style="display:block;"/></a>'
                        '</span>' %
                        (floatSide, int(x)+2, full_size_url,
             baseurl + '?id=' + image_name + '&size=' + px_size,
                         image_name, licensename[0]))
    else:
        x, y = getImageSize(pagename, photohandle, px_size, macro.request)

        if not border and not caption:
            img_string = ('<a href="%s">'
                          '<img class="borderless" src="%s" alt="%s" title="%s"/></a>' %
                          (full_size_url,
               baseurl + '?id=' + image_name + '&size=' + px_size,
                           image_name, licensename[0]))
        elif border and not caption:
            img_string = ('<a href="%s">'
                          '<img class="border" src="%s" alt="%s" title="%s"/></a>' %
                          (full_size_url,
               baseurl + '?id=' + image_name + '&size=' + px_size,
                           image_name, licensename[0]))
        elif border and caption:
            img_string = ('<a href="%s">'
                          '<img class="border" src="%s" alt="%s" title="%s"/></a>'
                          '<div style="width: %spx;">'
                          '<p class="normalCaption">%s</p></div>' %
                          (full_size_url,
               baseurl + '?id=' + image_name + '&size=' + px_size,
                           image_name, licensename[0], x, caption))
        elif not border and caption:
            img_string = ('<a href="%s">'
                          '<img class="borderless" src="%s" alt="%s" title="%s"/></a>'
                          '<div style="width: %spx;">'
                          '<p class="normalCaption">%s</p></div>' %
                          (full_size_url,
               baseurl + '?id=' + image_name + '&size=' + px_size,
                           image_name, licensename[0], x, caption))

        if alignment == 'right':
            img_string = '<span class="floatRight">' + img_string + '</span>'
        elif alignment == 'left':
            img_string = '<span class="floatLeft">' + img_string + '</span>'

        html.append(img_string)

    macro_text += ''.join(html)
    return macro_text

