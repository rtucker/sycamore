# -*- coding: utf-8 -*-

# Imports
from Sycamore import wikiutil
from Sycamore import config
from Sycamore.Page import Page

# can't really be cached right now, maybe later
# (use memcache and might not matter)
Dependencies = ["time"]

def execute(macro, args, formatter=None):
    formatter = macro.formatter
    pages = []
    if not args:
        pages.append(macro.formatter.page)
    else:
        pagenames = args.split(',')
        if pagenames[0] == 'or':
            outputtype = 'or'
            del(pagenames[0])
        elif pagenames[0] == 'and':
            outputtype = 'and'
            del(pagenames[0])
        else:
            outputtype = 'and'

        for pagename in pagenames:
            pages.append(Page(pagename, macro.request))

    # iterate through the pages, find links
    linkset = None
    for page in pages:
        links_here = page.getPageLinksTo()
        pages_deco = [(pagename.lower(), pagename) for pagename in links_here]
        pages_deco.sort()
        links_here = set([word for lower_word, word in pages_deco])
        if not linkset:
            linkset = links_here
        elif outputtype == 'and':
            linkset = linkset.intersection(links_here)
        elif outputtype == 'or':
            linkset = linkset.union(links_here)

    text = []
    if linkset:
        text.append(formatter.bullet_list(1))
        for link in linkset:
            text.append('%s%s%s' % (formatter.listitem(1),
                                    formatter.pagelink(link, generated=True),
                                    formatter.listitem(0)))
        text.append(formatter.bullet_list(0))
    
    return ''.join(text)
