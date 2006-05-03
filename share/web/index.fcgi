#!/usr/bin/python -OO
# -*- coding: iso-8859-1 -*-
"""
    Sycamore - FastCGI Driver Script

    @copyright: 2006 Philip Neustrom
    @license: GNU GPL, see COPYING for details.
"""

import sys, logging, os
__directory__ = os.path.dirname(__file__)
sys.path.extend([os.path.abspath(os.path.join(__directory__, '..', '..'))]),
# you may need to put something like this here if you don't have the required python modules in your path:
#sys.path.extend(['/home/philip/lib/python/'])

from Sycamore.support.wsgi_server.fcgi import WSGIServer
from Sycamore.request import RequestWSGI

def handle_request(env, start_response):
    request = RequestWSGI(env, start_response)
    return request.run()
    
if __name__ == '__main__':
    WSGIServer(handle_request, bindAddress=('localhost', 8882)).run()
