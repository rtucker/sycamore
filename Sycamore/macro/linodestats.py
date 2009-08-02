Dependencies = ["time"]

import string
import urllib
import xml.dom.minidom

from Sycamore.support import memcache

def execute(macro, args, formatter=None):
	if not formatter:
		formatter = macro.formatter
	try:
		mc = memcache.Client('127.0.0.1:11211')
		xmltree = mc.get("linodestats-rocwiki")
		status = 'cached'
		if not xmltree:
			statsfd = urllib.urlopen('http://www.linode.com/members/info/?user=rocwiki')
			xmltree = xml.dom.minidom.parseString(statsfd.read()).childNodes[0]
			status = 'fresh'
			mc.set("linodestats-rocwiki", time=600, val=xmltree)

		hostname = xmltree.getElementsByTagName('host')[0].getElementsByTagName('host')[0].childNodes[0].wholeText
		hostload = xmltree.getElementsByTagName('host')[0].getElementsByTagName('hostLoad')[0].childNodes[0].wholeText
		upsince = xmltree.getElementsByTagName('upSince')[0].childNodes[0].wholeText
		cpuconsumption = float(xmltree.getElementsByTagName('cpuConsumption')[0].childNodes[0].wholeText)
		totalbytes = int(xmltree.getElementsByTagName('bwdata')[0].getElementsByTagName('total_bytes')[0].childNodes[0].wholeText)
		timestamp = xmltree.getElementsByTagName('request')[0].getElementsByTagName('DateTimeStamp')[0].childNodes[0].wholeText

		loadavg = string.split(open('/proc/loadavg', 'r').readline())

		return formatter.rawHTML('<strong>VPS Stats</strong>: Host %s is <strong>%s</strong>.  Guest has been up since %s, and is averaging <strong>%2.2f</strong>%% of one host CPU.  Used <strong>%i GB</strong>.  Load averages are <strong>%s %s %s</strong>.  Host time is %s (%s).' % (hostname, hostload, upsince, cpuconsumption, totalbytes/1024/1024/1024, loadavg[0], loadavg[1], loadavg[2], timestamp, status))

	except:
		return formatter.rawHTML('<strong>VPS Stats</strong>: <a href="http://sadtrombone.com/">Unavailable</a>.')

