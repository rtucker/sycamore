#!/usr/bin/env python

# Returns a nifty box, suitable for hover-over popupping, with info from
# revip.info.

# This could be fed directly to JavaScript, but for https:// access, this
# keeps it all encrypted.

# Ryan Tucker <rtucker@gmail.com>, November 29 2010

# Imports
import cgi
import cgitb; cgitb.enable(display=0, logdir="/tmp")
import socket
import sys
import time
import urllib

try:
    import json
except:
    import simplejson as json

# Where am I?  Split argv[0] on /share and add the first half to the path.
sycamoreroot = sys.argv[0].split('/share')[0]
sys.path.append(sycamoreroot)
# Now import some stuff from Sycamore...
from Sycamore import config
from Sycamore.support import memcache

if config.memcache:
    mc = memcache.Client(config.memcache_servers)
else:
    mc = None

# Useful functions from:
# http://stackoverflow.com/questions/319279/how-to-validate-ip-address-in-python
def is_valid_ipv4_address(address):
    try:
        addr= socket.inet_pton(socket.AF_INET, address)
    except AttributeError: # no inet_pton here, sorry
        try:
            addr= socket.inet_aton(address)
        except socket.error:
            return False
        return address.count('.') == 3
    except socket.error: # not a valid address
        return False

    return True

def is_valid_ipv6_address(address):
    try:
        addr= socket.inet_pton(socket.AF_INET6, address)
    except socket.error: # not a valid address
        return False
    return True

# Print the HTTP header
sys.stdout.write("Content-type: text/html\n\n")

# Read and validate query parameter
form = cgi.FieldStorage()
if not (form.has_key("ip")):
    sys.stdout.write("<b>Error</b>: No IP specified\n")
    sys.exit(0)
else:
    ip = urllib.unquote_plus(form["ip"].value)

#if is_valid_ipv6_address(ip):
#    sys.stdout.write("<b>No IPv6 Support Yet</b>\n")
#    sys.stdout.write("<br>(it's probably RyanTucker)\n")
#    sys.exit(0)

if not is_valid_ipv4_address(ip) and not is_valid_ipv6_address(ip):
    sys.stdout.write("<b>Error</b>: not a valid IP address\n")
    sys.exit(0)

# Relay the query to revip.info
if mc:
    ipdata = mc.get('revip-query-info-' + ip)
else:
    ipdata = None

if not ipdata:
    ipjson = urllib.urlopen(url="http://revip.info/json/%s" % ip)
    ipdata = json.load(ipjson)
    ipdata['QueryTimestamp'] = int(time.time())
    if mc:
        mc.set('revip-query-info-' + ip, time=86400, val=ipdata)

# Start spitting it out...
sys.stdout.write("<table>")

if not (form.has_key("short")):
    outputorder = ['ReverseDNS', 'AsnNetwork', 'AsNumber', 'AsnOwner',
                   'AsnRegDate', 'AbuseContact', 'NetOwner', 'City',
                   'Province', 'PostalCode', 'Country', 'CountryCode',
                   'Latitude', 'Longitude', 'AreaCode', 'DomainCount',
                   'Domains', 'QueryTime', 'QueryTimestamp']
else:
    outputorder = ['NetOwner', 'City', 'Province', 'Country']

for key in outputorder:
    if key in ipdata.keys():
        if key is 'QueryTimestamp':
            timeago = int(time.time() - ipdata[key])
            value = ['%i seconds ago' % timeago]
        elif type(ipdata[key]) is list:
            value = ipdata[key]
        else:
            value = [ipdata[key]]

        for datum in value:
            sys.stdout.write("<tr><td><b>%s</b></td><td>&nbsp;</td><td>%s</td></tr>\n" %
                         (key, datum))

sys.stdout.write("</table>")

