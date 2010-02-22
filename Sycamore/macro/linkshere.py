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
        # use the current page
        pages.append(macro.formatter.page)
    else:
        pagenames = args.split(',')
        do_union = False
        if pagenames[0] == 'or':
            do_union = True
            del(pagenames[0])
        elif pagenames[0] == 'and':
            del(pagenames[0])

        for pagename in pagenames:
            pages.append(Page(pagename, macro.request))

    # iterate through the pages, find links
    linkset = None
    for page in pages:
        links_here = page.getPageLinksTo()
        pages_deco = [(pagename.lower(), pagename) for pagename in links_here]
        links_here = set([word for lower_word, word in pages_deco])
        if not linkset:
            # first time through
            linkset = links_here.copy()
        elif do_union:
            # OR the list
            linkset = linkset.union(links_here)
        else:
            # AND the list
            linkset = linkset.intersection(links_here)

    text = []
    if linkset:
        text.append(formatter.bullet_list(1))
        for link in sorted(linkset):
            text.append('%s%s%s' % (formatter.listitem(1),
                                    formatter.pagelink(link, generated=True),
                                    formatter.listitem(0)))
        text.append(formatter.bullet_list(0))
    
    return ''.join(text)
