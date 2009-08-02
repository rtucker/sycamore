# -*- coding: utf-8 -*-
"""
    Sycamore - RandomPage Macro

    @copyright: 2007 by Philip Neustrom <philipn@gmail.com>
    @copyright: 2000 by J�rgen Hermann <jh@web.de>
    @license: GNU GPL, see COPYING for details.

edited 2008/07/11 by rtucker - filtering out redirects and user pages

"""

# Imports
import random
from Sycamore import config
from Sycamore import wikiutil

from Sycamore.Page import Page

Dependencies = ["time"]

def execute(macro, args, formatter):
    if not formatter:
        formatter = macro.formatter
    # get number of wanted links        
    try:
        links = max(int(args), 1)
    except StandardError:
        links = 1

    # select the pages from the page list
    random_list = wikiutil.getRandomPages(macro.request)
    pages = []
    while len(pages) < links and random_list:
        pagename = random.choice(random_list)
        page = Page(pagename, macro.request)
        if macro.request.user.may.read(page) and page.exists() and not page.isRedirect():
		if page.proper_name()[0:6] != 'Users/' and page.proper_name()[-5:] != '/Talk':
	            pages.append(page)

    # return a single page link
    if links == 1:
        return pages[0].link_to()

    # return a list of page links
    pages.sort()
    result = [macro.formatter.bullet_list(1)]
    for page in pages:
        result.append("%s%s%s" %
                      (macro.formatter.listitem(1), page.link_to(),
                       macro.formatter.listitem(0)))
    result.append(macro.formatter.bullet_list(0))

    return ''.join(result)

