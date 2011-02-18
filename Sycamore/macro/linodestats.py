# Returns statistics for Linode VPS hosting.
# Must run within the Linode VPS itself, due to access control restrictions.
# Uses memcache for caching, to prevent excessive hits on Linode's API.

# Ryan Tucker <rtucker@gmail.com> for Project Sycamore

Dependencies = ["time"]

import string
import urllib
import xml.dom.minidom

from Sycamore.support import memcache
from Sycamore import config

def execute(macro, args, formatter=None):
    if not formatter:
        formatter = macro.formatter

    try:
        if config.memcache:
            mc = macro.request.mc
        else:
            return formatter.rawHTML('<strong>VPS Stats</strong>: Unavailable (requires memcache).')

        if config.linode_username:
            mc_key = 'linodestats-' + config.linode_username
            xmlurl = 'http://www.linode.com/members/info/?user=' + config.linode_username
        else:
            return formatter.rawHTML('<strong>VPS Stats</strong>: Unavailable (set linode_username in config)')

        xmltree = mc.get(mc_key)
        status = 'cached'
        if not xmltree:
            try:
                statsfd = urllib.urlopen(xmlurl)
                xmltree = xml.dom.minidom.parseString(statsfd.read()).childNodes[0]
            except:
                # it's missing
                return formatter.rawHTML('<strong>VPS Stats</strong>: Unavailable (XML error)')
            status = 'fresh'
            mc.set(mc_key, xmltree, time=600)

        # messy XML parsing action
        hostname = xmltree.getElementsByTagName('host')[0].getElementsByTagName('host')[0].childNodes[0].wholeText
        hostload = xmltree.getElementsByTagName('host')[0].getElementsByTagName('hostLoad')[0].childNodes[0].wholeText
        upsince = xmltree.getElementsByTagName('upSince')[0].childNodes[0].wholeText
        cpuconsumption = float(xmltree.getElementsByTagName('cpuConsumption')[0].childNodes[0].wholeText)
        totalbytes = int(xmltree.getElementsByTagName('bwdata')[0].getElementsByTagName('total_bytes')[0].childNodes[0].wholeText)
        timestamp = xmltree.getElementsByTagName('request')[0].getElementsByTagName('DateTimeStamp')[0].childNodes[0].wholeText

        loadavg = string.split(open('/proc/loadavg', 'r').readline())

        return formatter.rawHTML('<strong>VPS Stats</strong>: Host %s is <strong>%s</strong>.  Guest has been up since %s, and is averaging <strong>%2.2f</strong>%% of one host CPU.  Used <strong>%i GB</strong>.  Load averages are <strong>%s %s %s</strong>.  Host time is %s (%s).' % (hostname, hostload, upsince, cpuconsumption, totalbytes/1024/1024/1024, loadavg[0], loadavg[1], loadavg[2], timestamp, status))

    except IOError:
        return formatter.rawHTML('<strong>VPS Stats</strong>: Unavailable.')

