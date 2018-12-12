#!/usr/bin/env python
"""Perform one or several checks and play music using Chromecast if check fails.

Should be invoked after every configuration change by EEM.


Copyright (c) 2018 Cisco and/or its affiliates.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import argparse
import os
import re
import time
import threading
from urlparse import urlparse

from SimpleHTTPServer import BaseHTTPServer
from SimpleHTTPServer import SimpleHTTPRequestHandler

from cli import cli

import dns.resolver
import pychromecast
import requests

CASTIPADDR = '192.168.101.103'
AUDIOFILE = 'Future_Gladiator.mp3'

WEB_HOSTS = [
    'https://www.cisco.com',
    'https://www.google.com',
]

htdocs = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'htdocs')
os.chdir(htdocs)
server = BaseHTTPServer.HTTPServer(('0.0.0.0', 45114), SimpleHTTPRequestHandler)
thread = threading.Thread(target = server.serve_forever)
thread.daemon = True

def server_up():
    thread.start()
    print('starting server on port {}'.format(server.server_port))

def server_down():
    server.shutdown()
    print('stopping server on port {}'.format(server.server_port))

def audio_play():
    """Start playing music"""
    ship = cli("show ip int bri gi2")
    host = re.findall(r'[0-9]+(?:\.[0-9]+){3}', ship)[0]

    url = "http://{}:{}/{}".format(host, 45114, AUDIOFILE)

    cast = pychromecast.Chromecast(CASTIPADDR)
    mc = cast.media_controller
    mc.play_media(url, 'audio/mp3')


def send_syslog(message):
    """Sends a syslog message to the device with severity 6

    Args:
        message (str): message to be sent

    Returns:
        None
    """
    cli(
        'send log facility PYTHON severity 6 mnemonics CONF_CHECK '
        '{message}'.format(message=message)
    )


def parse_arguments():
    """Adds command-line argument parser"""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--chromecast', action="store_true", default=False,
        help='Play music using Chromecast if the checks fail'
    )
    parser.add_argument(
        '--syslog', action="store_true", default=False,
        help='Send syslog informational messages'
    )
    args = parser.parse_args()
    return args


def dns_check(urls, timeout=1, syslog=False):
    """Checks DNS resolutions to the list of URLs

    Args:
        urls (list): list of URLs to resolve DNS
        timeout (int): how long in seconds requests library will wait for
            a response from the URL
        syslog (boolean): True, if informational messages should be sent to
            the syslog

    Returns:
        boolean: True, if all DNS resolutions finished successfully
            False, if at least one DNS resolution failed
    """
    for url in urls:
        try:
            resolver = dns.resolver.Resolver()
            resolver.timeout = timeout
            resolver.lifetime = timeout
            domain = urlparse(url).hostname
            query = resolver.query(domain, 'A')
            message = 'DNS check for url {url} ... passed!'.format(url=url)
            print(message)
        except:
            message = (
                'DNS check for url {url} ... failed'.format(url=url)
            )
            print(message)
            if syslog:
                syslog_message = (
                    'DNS check for url {url} ... failed'.format(url=url)
                )
                send_syslog(syslog_message)
            return False
    else:
        message = "All dns checks passed successfully!"
        print(message)
        if syslog:
            send_syslog(message)
        return True


def web_check(urls, timeout=1, syslog=False):
    """Checks HTTP connections to the list of URLs

    Args:
        urls (list): list of URLs for requests to open HTTP connection to
        timeout (int): how long in seconds requests library will wait for
            a response from the URL
        syslog (boolean): True, if informational messages should be sent to
            the syslog

    Returns:
        boolean: True, if all HTTP requests finished successfully
            False, if at least one HTTP request failed
    """
    for url in urls:
        try:
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()
            message = 'Web check for url {url} ... passed!'.format(url=url)
            print(message)
        except requests.exceptions.RequestException as e:
            message = (
                'Web check for url {url} ... failed: '
                '{e.__class__.__name__}: {e}'.format(
                    url=url, e=e
                )
            )
            print(message)
            if syslog:
                syslog_message = (
                    'Web check for url {url} ... failed due to '
                    '{e.__class__.__name__}'.format(
                        url=url, e=e
                    )
                )
                send_syslog(syslog_message)
            return False
    else:
        message = "All web checks passed successfully!"
        print(message)
        if syslog:
            send_syslog(message)
        return True


def checks(syslog=False):
    """A batch of different checks to be performed

    Args:
        syslog (boolean): True, if informational messages should be sent to
            the syslog

    Raises:
        AssertionError: when one of the checks fails
    """
    assert dns_check(WEB_HOSTS, syslog=syslog)
    assert web_check(WEB_HOSTS, syslog=syslog)
    # More checks can be defined here


def main():
    args = parse_arguments()
    try:
        checks(args.syslog)
    except AssertionError:
        message = 'Network Error!'
        print(message)
        if args.syslog:
            send_syslog(message)
        if args.chromecast:
            server_up()
            audio_play()
            server_down()

if __name__ == '__main__':
    main()