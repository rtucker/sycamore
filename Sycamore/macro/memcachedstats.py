Dependencies = ["time"]

from Sycamore.support import memcache

def execute(macro, args, formatter=None):
	if not formatter:
		formatter = macro.formatter

	mc = memcache.Client(['127.0.0.1:11211'], debug=0)
	stats = mc.get_stats()[0][1]

	return formatter.rawHTML('<strong>Memcached Stats</strong>: Uptime <strong>%i</strong> hours, In/Out <strong>%i</strong>/<strong>%i</strong> MB, Total Gets <strong>%i</strong>, Get Hits <strong>%i</strong> (%2.2f percent), Get Misses <strong>%i</strong>, Total Items <strong>%i</strong>, Evictions <strong>%i</strong>.'
	 % (int(stats['uptime'])/60/60, int(stats['bytes_read'])/1024/1024, int(stats['bytes_written'])/1024/1024, int(stats['cmd_get']), int(stats['get_hits']), float(stats['get_hits'])/float(stats['cmd_get'])*100, int(stats['get_misses']), int(stats['curr_items']), int(stats['evictions'])))

