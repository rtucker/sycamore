import sys, string, os.path, re, time, threading, socket, random

from Sycamore import config, wikiutil
from Sycamore.Page import Page

quotes_re = re.compile('"(?P<phrase>[^"]+)"')

MAX_PROB_TERM_LENGTH = 64
DIVIDERS = '!"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~'
DIVIDERS_RE = r"""!"#$%&'()*+,-./:;<=>?@\[\\\]^_`{|}~"""

def make_id(pagename, wikiname):
  if config.wiki_farm:
    return "%s,%s" % (wikiutil.quoteFilename(wikiname), wikiutil.quoteFilename(pagename.lower()))
  else:
    return wikiutil.quoteFilename(pagename)

def get_id(id):
  if config.wiki_farm:
    id_split = id.split(',') 
    wikiname = wikiutil.unquoteFilename(id_split[0])
    pagename = wikiutil.unquoteFilename(id_split[1])
    return (pagename, wikiname)
  else:
    return wikiutil.unquoteFilename(id)

#word_characters = string.letters + string.digits
def build_regexp(terms):
  """builds a query out of the terms.  Takes care of things like "quoted text" properly"""
  regexp = []
  for term in terms:
    if type(term) == type([]):
      # an exactly-quoted sublist
      regexp.append('(((%s)|^)%s((%s)|$))' % (DIVIDERS_RE, ' '.join(term), DIVIDERS_RE))
    elif term:
      regexp.append('([%s]|^|\s)%s([%s]|$|\s)' % (DIVIDERS_RE, term, DIVIDERS_RE))

  regexp = re.compile('|'.join(regexp), re.IGNORECASE|re.UNICODE)

  return regexp

def find_num_matches(regexp, text):
  """
  Finds the number of occurances of regexp in text
  """
  i = 0
  loc = 0
  found = regexp.search(text)
  while found:
    i += 1
    loc += found.end()
    found = regexp.search(text[loc:])

  return i

def isdivider(w):
  """
  Does w contain a character/is a character that's a divider.  Examples are:  :,/-  etc.
  """
  for c in w:
    if c in DIVIDERS: return True
  return False

def iswhitespace(w):
  return not (w.strip() == w)

def isdivider_or_whitespace(w):
  return isdivider(w) or iswhitespace(w)

def notdivider_or_whitespace(w):
  return not isdivider_or_whitespace(w)

def _p_isalnum(c):
  return c.isalnum()

def _p_notalnum(c):
  return not _p_isalnum(c)

def _p_divider(c):
    return isdivider(c)

def _p_notdivider(c):
    return not _p_divider(c)

def notplusminus(c):
    return c != '+' and c != '-'

def _find_p(string, start, predicate):
    while start<len(string) and not predicate(string[start]):
        start += 1
    return start

class searchResult(object):
  def __init__(self, title, data, percentage, page_name, wiki_name):
    self.title = title
    self.data = data
    self.percentage = percentage
    self.page_name = page_name
    self.wiki_name = wiki_name

class SearchBase(object):
  def __init__(self, needles, request, p_start_loc=0, t_start_loc=0, num_results=10, wiki_global=False):
    self.request = request
    self.needles = needles
    self.p_start_loc = p_start_loc
    self.t_start_loc = t_start_loc
    self.num_results = 10
    self.wiki_global = wiki_global

    self.text_results = [] # list of searchResult objects
    self.title_results = [] # list of searchResult objects
    
  def _remove_junk(self, terms):
    # Cut each needle accordingly so that it returns good results. E.g. the user searches for "AM/PM" we want to cut this into "am" and "pm"
    nice_terms = []
    for term in terms:
      if type(term) == type([]):
        nice_terms.append(self._remove_junk(term))
        continue

      if not term.strip(): continue

      exact_match = False
      if not isdivider(term):
        nice_terms.append(term)
        continue

      if term.startswith('"') and term.endswith('"'):
        # we have an exact-match quote thing
        nice_terms.append(self._remove_junk(term.split())[1:-1])
        continue

      i = 0
      j = 0
      for c in term:
        if not isdivider(c):
          j += 1
          continue
        term_new = term[i:j].strip()
        if term_new: nice_terms.append(term_new)
        i = j+1
        j += 1
      term_new = term[i:j].strip()
      if term_new: nice_terms.append(term_new)

    return nice_terms

if config.has_xapian:
  import xapian
  class XapianSearch(SearchBase):
    def __init__(self, needles, request, p_start_loc=0, t_start_loc=0, num_results=10, db_location=None, processed_terms=None, wiki_global=False):
      SearchBase.__init__(self, needles, request, p_start_loc, t_start_loc, num_results, wiki_global=wiki_global)
  
      # load the databases
      if not db_location: db_location = config.search_db_location
      self.text_database = xapian.Database(os.path.join(db_location, 'text'))
      self.title_database = xapian.Database(os.path.join(db_location, 'title'))
            
      if not processed_terms:
        self.stemmer = xapian.Stem("english")
        self.terms = self._remove_junk(self._stem_terms(needles))
        self.printable_terms = needles
      else:
        self.terms = processed_terms

      if self.terms:
        self.query = self._build_query(self.terms)
      else:
        self.query = None
  
    def _stem_terms(self, terms):
      new_terms = []
      for term in terms:
        if type(term) == list:
          new_terms.append(self._stem_terms(term))
        else:
          term = term.lower().encode('utf-8')
          for term, pos in get_stemmed_text(term, self.stemmer):
            new_terms.append(term)
      return new_terms
      
  
    def _build_query(self, terms, op=xapian.Query.OP_OR):
      """builds a query out of the terms.  Takes care of things like "quoted text" properly"""
      query = None

      if type(terms[0]) == list:
        # an exactly-quoted sublist
        query = xapian.Query(xapian.Query.OP_PHRASE, terms[0])
      else:
        for term in terms:
          if query: query = xapian.Query(op, query, xapian.Query(op, [term]))
          else: query = xapian.Query(op, [term])
        
      if config.wiki_farm and not self.wiki_global:
        specific_wiki = xapian.Query(xapian.Query.OP_OR, [('F:%s' % self.request.config.wiki_name).encode('utf-8')])
        query = xapian.Query(xapian.Query.OP_AND, query, specific_wiki)

      return query
  
    def process(self):
      if not self.query: return
      # processes the search
      enquire = xapian.Enquire(self.text_database)
      enquire.set_query(self.query)
      t0 = time.time()
      matches = enquire.get_mset(self.p_start_loc, self.num_results+1)
      t1 = time.time()
      for match in matches:
        id = match[xapian.MSET_DOCUMENT].get_value(0)
        wiki_name = self.request.config.wiki_name
        if config.wiki_farm:
          title, wiki_name = get_id(id)
        else:
          title = get_id(id)
        page = Page(title, self.request, wiki_name=wiki_name)
        if not page.exists(): continue
        percentage = match[xapian.MSET_PERCENT]
        data = page.get_raw_body()
        search_item = searchResult(title, data, percentage, page.page_name, wiki_name)
        self.text_results.append(search_item)
  
      enquire = xapian.Enquire(self.title_database)
      enquire.set_query(self.query)
      matches = enquire.get_mset(self.t_start_loc, self.num_results+1)
      for match in matches:
        id = match[xapian.MSET_DOCUMENT].get_value(0)
        wiki_name = self.request.config.wiki_name
        if config.wiki_farm:
          title, wiki_name = get_id(id)
        else:
          title = get_id(id)
        page = Page(title, self.request, wiki_name=wiki_name)
        if not page.exists(): continue
        percentage = match[xapian.MSET_PERCENT]
        data = page.page_name
        search_item = searchResult(title, data, percentage, page.page_name, wiki_name)
        self.title_results.append(search_item)


  class RemoteSearch(XapianSearch):
    def __init__(self, needles, request, p_start_loc=0, t_start_loc=0, num_results=10, wiki_global=False):
      SearchBase.__init__(self, needles, request, p_start_loc, t_start_loc, num_results, wiki_global=wiki_global)

      self.stemmer = xapian.Stem("english")
      self.terms = self._remove_junk(self._stem_terms(needles))
      self.printable_terms = self._remove_junk(needles)

    def process(self):
      import socket, cPickle
      encoded_terms = [ wikiutil.quoteFilename(term) for term in self.terms ]
      server_address, server_port = config.remote_search
      s = socket.socket(socket.AF_INET, socket.SOCK_STREAM) 
      s.connect((server_address, server_port))

      output = s.makefile('w', 0)
      output.write('F\n')
      if self.wiki_global:
        output.write('*\n\n')
      else:
        output.write('%s\n\n' % self.request.config.wiki_name)
      output.write('S\n%s\n%s\n' % (self.p_start_loc, self.t_start_loc))
      for term in encoded_terms:
        output.write('%s\n' % term)
      output.write('\n')
      output.write('E\n\n') # end
      output.close()

      input = s.makefile('r', 0)
      for line in input:
        results_encoded = line.strip()
        break

      title_results, text_results = cPickle.loads(wikiutil.unquoteFilename(results_encoded))

      s.close()

      self.title_results = title_results
      self.text_results = text_results


class RegexpSearch(SearchBase):
  def __init__(self, needles, request, p_start_loc=0, t_start_loc=0, num_results=10, wiki_global=False):
    SearchBase.__init__(self, needles, request, p_start_loc, t_start_loc, num_results, wiki_global=wiki_global)

    self.terms = self._remove_junk(needles)
    self.printable_terms = self.terms
    self.regexp = build_regexp(self.terms)

  
  def process(self):
    # processes the search
    wiki_name = self.request.config.wiki_name
    if not self.wiki_global:
        wikis = [wiki_name]
    else:
        wikis = wikiutil.getWikiList(self.request)

    for wiki_name in wikis: 
        pagelist = wikiutil.getPageList(self.request)
        matches = []
        for pagename in pagelist:
          page = Page(pagename, self.request, wiki_name=wiki_name)
          text = page.get_raw_body()
          text_matches = find_num_matches(self.regexp, text)
          if text_matches:
            percentage = (text_matches*1.0/len(text.split()))*100
            self.text_results.append(searchResult(page.page_name, text, percentage, page.page_name, wiki_name)) 
          
          title = page.page_name
          title_matches = find_num_matches(self.regexp, title)
          if title_matches:
            percentage = (title_matches*1.0/len(title.split()))*100
            self.title_results.append(searchResult(title, title, percentage, page.page_name, wiki_name))

        # sort the title and text results by relevancy
        self.title_results.sort(lambda x,y: cmp(y.percentage, x.percentage))
        self.text_results.sort(lambda x,y: cmp(y.percentage, x.percentage))

        # normalize the percentages.  still gives shit, but what can you expect from regexp..install xapian!
        if self.title_results:
          i = 0
          max_title_percentage = self.title_results[0].percentage
          self.title_results = self.title_results[self.t_start_loc:self.t_start_loc+self.num_results+1]
          for title in self.title_results:
            if i > self.num_results: break
            title.percentage = (title.percentage/max_title_percentage)*100
            i += 1

        if self.text_results: 
          i = 0 
          max_text_percentage = self.text_results[0].percentage
          self.text_results = self.text_results[self.p_start_loc:self.p_start_loc+self.num_results+1]
          for text in self.text_results:
            if i > self.num_results: break
            text.percentage = (text.percentage/max_text_percentage)*100
            i += 1

def get_stemmed_text(text, stemmer):
  """
  Returns a stemmed version of text.
  """
  postings = []
  pos = 0
  # At each point, find the next alnum character (i), then
  # find the first non-alnum character after that (j). Find
  # the first non-plusminus character after that (k), and if
  # k is non-alnum (or is off the end of the para), set j=k.
  # The term generation string is [i,j), so len = j-i

  i = 0
  while i < len(text):
      i = _find_p(text, i, notdivider_or_whitespace)
      j = _find_p(text, i, isdivider_or_whitespace)
      k = _find_p(text, j, notplusminus)
      if k == len(text) or not notdivider_or_whitespace(text[k]):
          j = k
      if (j - i) <= MAX_PROB_TERM_LENGTH and j > i:
          term = stemmer.stem_word(text[i:j].lower())
          postings.append((term, pos)) 
          pos += 1
      i = j
  return postings


def _do_postings(doc, text, id, stemmer, request):
  """
  Does positional indexing.
  """

  # unique id     
  # NOTE on unique id:  we assume this is unique and not creatable via the user.  We consider 'q:this' to split as q, this -- so this shouldn't be exploitable.
  # The reason we use such a unique id is that it's the easiest way to do this using xapian.
  id = id.encode('utf-8')
  text = text.encode('utf-8')
  doc.add_term(("Q:%s" % id).encode('utf-8'))
  if config.wiki_farm:
    doc.add_term(("F:%s" % request.config.wiki_name).encode('utf-8'))

  doc.add_value(0, id)

  for term, pos in get_stemmed_text(text, stemmer):
    doc.add_posting(term, pos)


def _search_sleep_time():
    """
    Sleep for a bit before trying to hit the db again. 
    """
    sleeptime = 0.1 + random.uniform(0, .05)
    time.sleep(sleeptime)    


def add_to_remote_index(page):
  server_address, server_port = config.remote_search
  s = socket.socket(socket.AF_INET, socket.SOCK_STREAM) 
  s.connect((server_address, server_port))

  output = s.makefile('w', 0)
  output.write('F\n')
  output.write('%s\n\n' % page.wiki_name)
  output.write('A\n')
  output.write('%s\n' % wikiutil.quoteFilename(page.page_name))
  output.write('\n')
  output.write('E\n\n') # end
  output.close()

  s.close() 


def add_to_index(page, db_location=None, text_db=None, title_db=None, try_remote=True):
  """Add page to the search index"""
  if not config.has_xapian: return
  if not db_location: db_location = config.search_db_location
  if try_remote and config.remote_search:
    threading.Thread(target=add_to_remote_index, args=(page,)).start()
  else:
    index(page, db_location=db_location, text_db=text_db, title_db=title_db)

def index(page, db_location=None, text_db=None, title_db=None):
  """Don't call this function.  Call add_to_index."""
  if not page.exists(): return
  stemmer = xapian.Stem("english")

  if not title_db:
    while 1:
        try:
            database = xapian.WritableDatabase(
              os.path.join(db_location, 'title'),
              xapian.DB_CREATE_OR_OPEN)
        except IOError, err:
            strerr = str(err) 
            if strerr == 'DatabaseLockError: Unable to acquire database write lock %s' % os.path.join(os.path.join(db_location, 'title'), 'db_lock'):
                if config.remote_search:
                    # we shouldn't try again if we're using remote db
                    raise IOError, err 
                _search_sleep_time()
            else:
                raise IOError, err
        else:
            break
  else: database = title_db
    
  text = page.page_name.encode('utf-8')
  pagename = page.page_name.encode('utf-8')
  id = make_id(pagename, page.request.config.wiki_name)
  doc = xapian.Document()
  _do_postings(doc, text, id, stemmer, page.request)
  database.replace_document("Q:%s" % id, doc)

  if not text_db:
    while 1:
        try:
            database = xapian.WritableDatabase(
              os.path.join(db_location, 'text'),
              xapian.DB_CREATE_OR_OPEN)
        except IOError, err:
            strerr = str(err) 
            if strerr == 'DatabaseLockError: Unable to acquire database write lock %s' % os.path.join(os.path.join(db_location, 'text'), 'db_lock'):
                if config.remote_search:
                    # we shouldn't try again if we're using remote db
                    raise IOError, err 
                _search_sleep_time()
            else:
                raise IOError, err
        else:
            break

  else: database = text_db

  text = page.get_raw_body()
  doc = xapian.Document()
  _do_postings(doc, text, id, stemmer, page.request)
  database.replace_document("Q:%s" % id, doc)

def remove_from_remote_index(page):
  server_address, server_port = config.remote_search
  s = socket.socket(socket.AF_INET, socket.SOCK_STREAM) 
  s.connect((server_address, server_port))

  output = s.makefile('w', 0)
  output.write('F\n')
  output.write('%s\n\n' % page.request.config.wiki_name)
  output.write('D\n')
  output.write('%s\n' % wikiutil.quoteFilename(page.page_name))
  output.write('\n')
  output.write('E\n\n') # end
  output.close()

  s.close() 

def remove_from_index(page, db_location=None, text_db=None, title_db=None):
  """removes the page from the index.  call this on page deletion.  all other page changes can just call index(). """
  if not config.has_xapian: return
  if not db_location: db_location = config.search_db_location
  if config.remote_search:
    threading.Thread(target=remove_from_remote_index, args=(page,)).start()
  else:
    remove(page, db_location=db_location, text_db=text_db, title_db=title_db)

def remove(page, db_location=None, text_db=None, title_db=None):
  """Don't call this function.  Call remove_from_index."""
  pagename = page.page_name.encode('utf-8')
  id = make_id(pagename, page.request.config.wiki_name)
  while 1:
    try:
        database = xapian.WritableDatabase(
          os.path.join(db_location, 'title'),
          xapian.DB_CREATE_OR_OPEN)
    except IOError, err:
        strerr = str(err) 
        if strerr == 'DatabaseLockError: Unable to acquire database write lock %s' % os.path.join(os.path.join(db_location, 'title'), 'db_lock'):
            if config.remote_search:
                # we shouldn't try again if we're using remote db
                raise IOError, err 
            _search_sleep_time()
        else:
            raise IOError, err
    else:
        break


  database.delete_document("Q:%s" % id)

  while 1:
    try:
        database = xapian.WritableDatabase(
          os.path.join(db_location, 'text'),
          xapian.DB_CREATE_OR_OPEN)
    except IOError, err:
        strerr = str(err) 
        if strerr == 'DatabaseLockError: Unable to acquire database write lock %s' % os.path.join(os.path.join(db_location, 'text'), 'db_lock'):
            if config.remote_search:
                # we shouldn't try again if we're using remote db
                raise IOError, err 
            _search_sleep_time()
        else:
            raise IOError, err
    else:
        break

  database.delete_document("Q:%s" % id)

def prepare_search_needle(needle):
  """Basically just turns a string of "terms like this" and turns it into a form usable by Search(), paying attention to "quoted subsections" for exact matches."""
  if config.has_xapian:
    stemmer = xapian.Stem("english")
  else:
    stemmer = None
    
  new_list = []
  quotes = quotes_re.finditer(needle)
  i = 0
  had_quote = False
  for quote in quotes:
    had_quote = True
    non_quoted_part = needle[i:quote.start()].strip().split()
    if non_quoted_part: new_list += non_quoted_part
    i = quote.end()
    new_phrase = []
    phrase = quote.group('phrase').split()
    phrase = new_phrase
    new_list.append(phrase)
  else:
    needles = needle.encode('utf-8').split()
    new_needle = needles

  if had_quote:
    new_needle = new_list

  return new_needle


if config.has_xapian:
  if config.remote_search:
    Search = RemoteSearch 
  else:
    Search = XapianSearch
else: Search = RegexpSearch
