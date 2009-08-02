#!/usr/bin/python

# TODO: Limit it to < 1 week
# TODO: Error trapping

Dependencies = ["time"]

import simplejson
import time
import urllib

from Sycamore.support import memcache
from Sycamore import wikiutil

SOCKET_TIMEOUT = 5 # in the event twitter is missing

# from http://snipplr.com/view.php?codeview&id=5713
def elapsed_time(seconds, suffixes=['year','week','day','hour','minute','second'], add_s=True, separator=' '):
	"""
	Takes an amount of seconds and turns it into a human-readable amount of time.
	"""
	# the formatted time string to be returned
	time = []
	
	# the pieces of time to iterate over (days, hours, minutes, etc)
	# - the first piece in each tuple is the suffix (d, h, w)
	# - the second piece is the length in seconds (a day is 60s * 60m * 24h)
	parts = [(suffixes[0], 60 * 60 * 24 * 7 * 52),
		  (suffixes[1], 60 * 60 * 24 * 7),
		  (suffixes[2], 60 * 60 * 24),
		  (suffixes[3], 60 * 60),
		  (suffixes[4], 60),
		  (suffixes[5], 1)]
	
	# for each time piece, grab the value and remaining seconds, and add it to
	# the time string
	for suffix, length in parts:
		value = seconds / length
		if value > 0 and len(time) < 2:
			seconds = seconds % length
			time.append('%s %s' % (str(value),
					       (suffix, (suffix, suffix + 's')[value > 1])[add_s]))
		if seconds < 1:
			break
	
	return separator.join(time)

def execute(macro, args, formatter=None, test=None):
	if not formatter:
		formatter = macro.formatter

	mc = memcache.Client('127.0.0.1:11211')

	if args:
		query = args
	else:
		query = 'rocwiki'

	maxlines = '3'
	maxseconds = 3*24*60*60

	# get the info from search.twitter.com
	class AppURLopener(urllib.FancyURLopener):
	    version = "SycamoreSummizeMacro/1.7 (http://rocwiki.org/)"

	urllib._urlopener = AppURLopener()

	localonly=1
	fromcache = 'yes'
	response_dict = mc.get("twitter-local-" + urllib.quote(query))
	if not response_dict:
		fromcache = 'no'
		response_dict = simplejson.loads(urllib.urlopen('http://search.twitter.com/search.json?geocode=43.1%2C-77.6%2C100km&q=' + urllib.quote(query) + '&rpp=' + maxlines).read())
		mc.set("twitter-local-" + urllib.quote(query), time=3600, val=response_dict)
	#if len(response_dict['results']) == 0:
	#	localonly=0
	#	# open it up a bit
	#	response_dict = simplejson.loads(urllib.urlopen('http://search.twitter.com/search.json?q=' + urllib.quote(query) + '&rpp=' + maxlines).read())

	if len(response_dict['results']) > 0:
		display_list = []
		for i in response_dict['results']:
			name = i['from_user']
			text = wikiutil.simpleStrip(macro.request, i['text']).replace('&amp;','&')
			try:
				location = ' from ' + i['location']
			except KeyError:
				location = ''
			created = time.mktime(time.strptime(i['created_at'], '%a, %d %b %Y %H:%M:%S +0000'))
			created_seconds_ago = int(time.mktime(time.gmtime()) - created)
			id = i['id']
			link = 'http://twitter.com/' + name + '/statuses/' + `id`
			if created_seconds_ago < maxseconds:
				display_list.append('||' + text + ' [http://twitter.com/' + name + ' ' + name + ']' + location + ', [' + link + ' ' + elapsed_time(created_seconds_ago) + ' ago]||\n')
			#else:
			#	display_list.append('||TOO OLD: ' + `created_seconds_ago` + ' vs ' + `maxseconds` + ' ' + text + ' [http://twitter.com/' + name + ' ' + name + ']' + location + ', [' + link + ' ' + elapsed_time(created_seconds_ago) + ' ago]||\n')

	else:
		if localonly:
			display_list = ['||Nothing locally about ' + query + ' on [http://twitter.com/ twitter] lately... maybe you should go stir something up.||\n']
		else:
			display_list = ['||Nothing about ' + query + ' *anywhere* on [http://twitter.com/ twitter] lately... maybe you should go stir something up.||\n']
		display_list = []

	if localonly:
		outstring = "||<bgcolor='#E0E0FF'>'''Twitter traffic about [http://search.twitter.com/search?q=" + urllib.quote_plus(query) + " " + query + "]'''||\n"
	else:
		outstring = "||<bgcolor='#E0E0FF'>'''Global Twitter traffic about [http://search.twitter.com/search?q=" + urllib.quote_plus(query) + " " + query + "]'''||\n"
	for i in display_list:
		outstring = outstring + i

	if not test:
		if display_list != []:
			return wikiutil.wikifyString(outstring, macro.request, formatter.page, strong=True)
		else:
			return wikiutil.wikifyString('### Twitter results for ' + query + ' would go here', macro.request, formatter.page, strong=True)
	else:
		if display_list != []:
			print outstring

	return 0

if __name__ == '__main__':
	execute('', '', 'Blah', True)

