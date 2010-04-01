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
    debug = []
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

        lastpage = []
        for pagename in pagenames:
            curpage = Page(pagename, macro.request)
            if not curpage.exists():
                # The page doesn't exist.  Either someone's making
                # stuff up, or there's a comma in the page name.
                debug.append('<!-- "%s" does not exist -->' % curpage.page_name)
                if lastpage:
                    # We have something to try from last time.
                    lastpage.append(pagename)
                    debug.append('<!-- trying "%s" -->' % ','.join(lastpage))
                    curpage = Page(','.join(lastpage), macro.request)
                    if curpage.exists():
                        # awesome!
                        debug.append('<!-- "%s" does exist -->' % curpage.page_name)
                        lastpage = []
                        pages.append(curpage)
                else:
                    debug.append('<!-- "%s" appended to rescanner -->' % pagename)
                    lastpage.append(pagename)
            else:
                debug.append('<!-- "%s" does exist -->' % curpage.page_name)
                lastpage = []
                pages.append(curpage)

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
        debug.append('<!-- DEBUG: "%s" yielded %i links -->' % (page.page_name, len(links_here)))

    text = []
    if linkset:
        text.append(formatter.bullet_list(1))
        for link in sorted(linkset):
            text.append('%s%s%s' % (formatter.listitem(1),
                                    formatter.pagelink(link, generated=True),
                                    formatter.listitem(0)))
        text.append(formatter.bullet_list(0))

    text.extend(debug)
    
    return ''.join(text)
