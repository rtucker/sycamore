# Displays vital stats for memcached.
# Ryan Tucker <rtucker@gmail.com> for Sycamore

Dependencies = ["time"]

from Sycamore.support import memcache
from Sycamore import config

def execute(macro, args, formatter=None):
	if not formatter:
		formatter = macro.formatter

	# If we aren't using memcached, skip this plugin
	if not config.memcache: return formatter.rawHTML('')

	# Initialize our counter and output string
	counter = 0
	out = '<strong>Memcached Stats</strong>:<br>'

	# Iterate through all of the memcached servers
	for memserver in config.memcache_servers:
		# Connect and fetch stats
		mc = memcache.Client([memserver], debug=0)
		stats = mc.get_stats()[0][1]

		# Prepare the output for display
		counter += 1
		out += """&nbsp;&nbsp;&nbsp;&nbsp;
	Instance <strong>%s</strong>:
	Uptime <strong>%i</strong> hours,
	In/Out <strong>%i</strong>/<strong>%i</strong> MB,
	Total Gets <strong>%i</strong>,
	Get Hits <strong>%i</strong> (%2.2f percent),
	Get Misses <strong>%i</strong>,
	Total Items <strong>%i</strong>,
	Evictions <strong>%i</strong>.<br>""" % (
		int(counter),
		int(stats['uptime'])/60/60,
		int(stats['bytes_read'])/1024/1024,
		int(stats['bytes_written'])/1024/1024,
		int(stats['cmd_get']),
		int(stats['get_hits']),
		float(stats['get_hits'])/float(stats['cmd_get'])*100,
		int(stats['get_misses']),
		int(stats['curr_items']),
		int(stats['evictions']))

	# When done, return the output!
	return formatter.rawHTML(out)

