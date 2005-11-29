"""
    LocalWiki - IncludePages macro
    
    Copyright (c) 2003 by Jun Hu <j.hu@tue.nl>

    Copyright (c) 2002 by Michael Reinsch <mr@uue.org>
    All rights reserved, see COPYING for details.

    Code based on the LocalWiki PageList macro
    Copyright (c) 2000, 2001, 2002 by J¨¹rgen Hermann <jh@web.de>

    This macro includes the formatted content of the given pages, following
    recursive includes if encountered. Cycles are detected!

    It uses the LocalWiki Include macro which does the real work.

    Usage:
        [[IncludePages(pagepattern,level, sort=ascending|descending, items=n)]]

        pagepattern Pattern of the page(s) to include
        level       Level (1..5) of the generated heading (optional)
        sort        Sorting order (optional). 
        items       Maximum number of pages to include. 
        
        The headings for the included pages will be generated from the page
        names

    Examples:
        [[IncludePages(FooBar/20.*)]]
           -- includes all pages which start with FooBar/20 this is usefull
              in combination with the MonthCalendar macro

        [[IncludePages(FooBar/20.*, 2)]]
           -- set level to 2 (default is 1)
           
        [[IncludePages(FooBar/20.*, 2, sort=descending]]
           -- reverse the ordering (default is ascending)
       
        [[IncludePages(FooBar/20.*, 2, sort=descending, items=1]]
           -- Only the last item will be included.

    $Id$
"""

import re
#from LocalWiki import user
from LocalWiki import config
from LocalWiki import wikiutil
#from LocalWiki.i18n import _
import LocalWiki.macro.Include

_arg_level = r',\s*(?P<level>\d+)'
_arg_sort = r'(,\s*sort=(?P<sort>(ascending|descending)))?'
_arg_items = r'(,\s*items=(?P<items>\d+))?'
_args_re_pattern = r'^(?P<pattern>[^,]+)((%s)?%s%s)?$' % (_arg_level,_arg_sort,_arg_items)

def execute(macro, text, args_re=re.compile(_args_re_pattern)):
    ret = ''

    # parse and check arguments
    args = args_re.match(text)
    if not args:
        return ('<p><strong class="error">%s</strong></p>' %
            _('Invalid include arguments "%s"!')) % (text,)

    # get the pages
    inc_pattern = args.group('pattern')
    if args.group('level'):
        level = int(args.group('level'))
    else:
        level = 1

    try:
        needle_re = re.compile(inc_pattern, re.IGNORECASE)
    except re.error, e:
        return ('<p><strong class="error">%s</strong></p>' %
            _("ERROR in regex '%s'") % (inc_pattern,), e)

    all_pages = wikiutil.getPageList()
    hits = filter(needle_re.search, all_pages)
    hits.sort()
    sort_dir = args.group('sort')
    if sort_dir == 'descending':
        hits.reverse()
    max_items = args.group('items')
    if max_items:
        hits = hits[:int(max_items)]

    for inc_name in hits:
        params = '%s,"%s",%s' % (inc_name,inc_name, level)
        ret = ret +"<p>"+ LocalWiki.macro.Include.execute(macro, params) +"\n"

    # return include text
    return ret
