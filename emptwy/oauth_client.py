#!/usr/bin/env python
# coding: utf-8

# Copyright (c) 2011, Renzo Carbonara <gnuk0001@gmail.com>
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#     * Redistributions of source code must retain the above copyright notice,
#       this list of conditions and the following disclaimer.
#
#     * Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#
#     * Neither the name of the Renzo Carbonara nor the names of its
#       contributors may be used to endorse or promote products derived from
#       this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON
# ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

"""
A generic command-line OAuth client.
"""

import sys
import logging
from urlparse import parse_qsl

import oauth2 as oauth


log = logging.getLogger(__file__)



def oauth_ask_user_authorization(authorize_url, request_token_key):
    print u"Go to the following URL in your browser, authorize the application, and get the verification code:\n\t" \
          u"%s?oauth_token=%s" % (authorize_url, request_token_key)
    oauth_verifier = raw_input(u"Enter the verification code: ")

    return oauth_verifier


def build_authorized_oauth_client(request_token_url, access_token_url, authorize_url,
                                  consumer_key, consumer_secret,
                                  request_token_key=None, request_token_secret=None,
                                  access_token_key=None, access_token_secret=None,
                                  ask_user_authorization_callback=oauth_ask_user_authorization):
    """
    Returns an authorized OAuth client for a consumer at the given URLs.

    If Access Token is given, then build a client with that token.

    Else, if Request Token is given, then authorize that token, get an Access
    Token from it, and build a client with it.

    Else, get a Request Token, authorize that token, get an Access Token from
    it, and build a client with it.
    """
    consumer = oauth.Consumer(key=consumer_key, secret=consumer_secret)
    client = oauth.Client(consumer)

    if not (access_token_key and access_token_secret):

        if not (request_token_key and request_token_secret):
            # Get unauthorized Request Token
            log.debug(u"Getting OAuth Request Token")
            resp, content = client.request(request_token_url, "GET")
            rt = dict(parse_qsl(content))
            request_token_key, request_token_secret = rt['oauth_token'], rt['oauth_token_secret']
            log.debug(u"Got OAuth Request Token. Key '%s', Secret '%s'" % (request_token_key, request_token_secret))

        # Ask user for Request Token authorization
        log.debug(u"Asking user for OAuth authorization for Request Token key '%s'" % request_token_key)
        oauth_verifier = oauth_ask_user_authorization(authorize_url, request_token_key)
        log.debug(u"Got OAuth verifier '%s' for Request token Key '%s'" % (oauth_verifier, request_token_key))

        # Build authorized Request Token
        request_token = oauth.Token(request_token_key, request_token_secret)
        request_token.set_verifier(oauth_verifier)
        client.token = request_token

        # Get Access Token
        log.debug(u"Getting OAuth Access Token")
        resp, content = client.request(access_token_url, "POST")
        at = dict(parse_qsl(content))
        access_token_key, access_token_secret = at['oauth_token'], at['oauth_token_secret']
        log.debug(u"Got OAuth Access Token. Key '%s', Secret '%s'" % (access_token_key, access_token_secret))

    client.token = oauth.Token(access_token_key, access_token_secret)
    return client


def parse_args():
    import argparse

    parser = argparse.ArgumentParser(description=u"OAuth client")

    # URLs
    parser.add_argument('--request-token-url', required=True,
                        dest='request_token_url', type=str, action='store')
    parser.add_argument('--access-token-url', required=True,
                        dest='access_token_url', type=str, action='store')
    parser.add_argument('--authorize-url', required=True,
                        dest='authorize_url', type=str, action='store')

    # Consumer
    parser.add_argument('--consumer-key', required=True,
                        dest='consumer_key', type=str, action='store')
    parser.add_argument('--consumer-secret', required=True,
                        dest='consumer_secret', type=str, action='store')

    # Tokens
    parser.add_argument('--request-token-key', required=False,
                        dest='request_token_key', type=str, action='store')
    parser.add_argument('--request-token-secret', required=False,
                        dest='request_token_secret', type=str, action='store')

    parser.add_argument('--access-token-key', required=False,
                        dest='access_token_key', type=str, action='store')
    parser.add_argument('--access-token-secret', required=False,
                        dest='access_token_secret', type=str, action='store')

    # Misc
    parser.add_argument('--outfile', '-o', metavar='FILE', default=sys.stdout,
                        dest='outfile', type=argparse.FileType('wb'), action='store')
    parser.add_argument('--debug', dest='debug', default=False, action='store_true',
                        help=u"Show debug information")
    parser.add_argument('--quiet', dest='quiet', default=False, action='store_true',
                        help=u"Only show fatal errors")

    # Resource URL
    parser.add_argument('method', type=str, action='store',
                        help=u"Resource HTTP method")

    parser.add_argument('url', type=str, action='store',
                        help=u"Resource URL")

    args = parser.parse_args()

    if args.request_token_key and not args.request_token_secret:
            parser.error(u"Missing '--request-token-secret'")

    if args.access_token_key and not args.access_token_secret:
            parser.error(u"Missing '--access-token-secret'")

    return args


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    import argparse

    args = parse_args()
    if args.debug:
        log.setLevel(logging.DEBUG)
    if args.quiet:
        log.setLevel(logging.FATAL)

    client = build_authorized_oauth_client(
        request_token_url=args.request_token_url,
        access_token_url=args.access_token_url,
        authorize_url=args.authorize_url,
        consumer_key=args.consumer_key,
        consumer_secret=args.consumer_secret,
        request_token_key=args.request_token_key,
        request_token_secret=args.request_token_secret,
        access_token_key=args.access_token_key,
        access_token_secret=args.access_token_secret)

    log.debug(u"Requesting resource: %s %s" % (args.method, args.url))
    resp, content = client.request(args.url, args.method)

    log.info(u"Response info: %s" % repr(resp))
    args.outfile.write(content)
    args.outfile.flush()

