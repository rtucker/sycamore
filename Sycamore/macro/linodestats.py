# Returns statistics for Linode VPS hosting.
# Must run within the Linode VPS itself, due to access control restrictions.
# Uses memcache for caching, to prevent excessive hits on Linode's API.

# Ryan Tucker <rtucker@gmail.com> for Project Sycamore

Dependencies = ["time"]

import string
import urllib2
import xml.dom.minidom

from Sycamore.support import memcache
from Sycamore import config

# The undocumented stats API doesn't work with IPv6 yet, so we'll kinda
# do this crazy thing.
# http://stackoverflow.com/questions/2014534/force-python-mechanize-urllib2-to-only-use-a-requests
import socket
origGetAddrInfo = socket.getaddrinfo

def getAddrInfoWrapper(host, port, family=0, socktype=0, proto=0, flags=0):
    return origGetAddrInfo(host, port, socket.AF_INET, socktype, proto, flags)

socket.getaddrinfo = getAddrInfoWrapper
# End crazy thing

def execute(macro, args, formatter=None):
    stats = {}
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
        if not xmltree:
            try:
                statsfd = urllib2.urlopen(xmlurl)
                xmltree = xml.dom.minidom.parseString(statsfd.read()).childNodes[0]
                # make sure we have useful stuff here
                host = xmltree.getElementsByTagName('host')[0]
            except:
                # it's missing
                return formatter.rawHTML('<strong>VPS Stats</strong>: Unavailable (XML error)')
            mc.set(mc_key, xmltree, time=600)

        # messy XML parsing action
        try:
            upsince = xmltree.getElementsByTagName('upSince')[0]
            bwdata = xmltree.getElementsByTagName('bwdata')[0]
            request = xmltree.getElementsByTagName('request')[0]
            host = xmltree.getElementsByTagName('host')[0]
            stats['host'] = host.getElementsByTagName('host')[0].childNodes[0].wholeText
            stats['pendingJobs'] = int(host.getElementsByTagName('pendingJobs')[0].childNodes[0].wholeText)
            if stats['pendingJobs'] == 1:
                stats['pJs'] = ''
            else:
                stats['pJs'] = 's'
            stats['upSince'] = upsince.childNodes[0].wholeText
            stats['total_bytes'] = int(bwdata.getElementsByTagName('total_bytes')[0].childNodes[0].wholeText)
            stats['total_gb'] = float(stats['total_bytes'])/1024/1024/1024
            stats['max_avail'] = int(bwdata.getElementsByTagName('max_avail')[0].childNodes[0].wholeText)
            stats['rx_bytes'] = int(bwdata.getElementsByTagName('rx_bytes')[0].childNodes[0].wholeText)
            stats['tx_bytes'] = int(bwdata.getElementsByTagName('tx_bytes')[0].childNodes[0].wholeText)
            stats['tx_perc'] = float(stats['tx_bytes'])/float(stats['total_bytes'])*100
            stats['rx_perc'] = float(stats['rx_bytes'])/float(stats['total_bytes'])*100
            stats['bw_perc'] = float(stats['total_bytes'])/float(stats['max_avail'])*100
            stats['DateTimeStamp'] = request.getElementsByTagName('DateTimeStamp')[0].childNodes[0].wholeText
            loadavg = string.split(open('/proc/loadavg', 'r').readline())
            stats['loadavg'] = '%s %s %s' % (loadavg[0], loadavg[1], loadavg[2])
        except Exception, e:
            return formatter.rawHTML('<strong>VPS Stats</strong>: Unavailable (XML element parsing error) <!-- %s -->' % e)

        return formatter.rawHTML("""
          <strong>VPS Stats</strong>:<br>&nbsp;&nbsp;&nbsp;&nbsp;
          At %(DateTimeStamp)s, host %(host)s has
          <strong>%(pendingJobs)i</strong> pending job%(pJs)s.  This instance
          has been running since %(upSince)s, with load averages
          <strong>%(loadavg)s</strong>.  This month's bandwidth consumption
          has been <strong>%(total_gb)2.2f GB</strong>, or %(bw_perc)2.2f%%
          of the monthly quota.  Outbound data has accounted for
          <strong>%(tx_perc)2.2f%%</strong> of that total.
        """ % stats)

    except IOError:
        return formatter.rawHTML('<strong>VPS Stats</strong>: Unavailable.')

