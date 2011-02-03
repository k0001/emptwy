# coding: utf-8

import gevent.monkey; gevent.monkey.patch_all()

import json
import logging
import urllib

import gevent
import gevent.queue

from emptwy.oauth_client import build_authorized_oauth_client

log = logging.getLogger(__file__)


OAUTH_REQUEST_TOKEN_URL   = "http://twitter.com/oauth/request_token"
OAUTH_ACCESS_TOKEN_URL    = "http://twitter.com/oauth/access_token"
OAUTH_AUTHORIZE_URL       = "http://twitter.com/oauth/authorize"


class TwitterResponseError(Exception):
    pass


def twitter_get_user_timeline(oauth_client_builder, screen_name, include_rts=True, page=0, count=200):
    if page < 0:
        raise ValueError(u"page must be positive")
    if not 0 < count <= 200:
        raise ValueError(u"count must be in range (0, 200]")

    params = {
        'screen_name': screen_name,
        'trim_user': 1,
        'count': count,
        'page': page,
        'include_rts': 1 if include_rts else 0 }
    url = 'http://api.twitter.com/1/statuses/user_timeline.json?' + urllib.urlencode(params)

    oauth_client = oauth_client_builder()

    log.debug(u"Requesting GET {}".format(url))
    resp, content = oauth_client.request(url, 'GET')

    log.debug(u"Response info: {}".format(resp))
    if not 200 <= int(resp['status']) < 400:
        raise TwitterResponseError(resp['status'])

    statuses = json.loads(content)
    return statuses


def twitter_destroy_status(oauth_client_builder, status_id):
    url = 'http://api.twitter.com/1/statuses/destroy/{:d}.json'.format(status_id)

    oauth_client = oauth_client_builder()

    log.debug(u"Requesting POST {}".format(url))
    resp, content = oauth_client.request(url, 'POST')

    log.debug(u"Response info: {}".format(resp))
    if not 200 <= int(resp['status']) < 400:
        raise TwitterResponseError(resp['status'])

    return json.loads(content)


def delete_tweets_page(oauth_client_builder, screen_name, num_workers=5, **kwargs):
    statuses = twitter_get_user_timeline(oauth_client_builder, screen_name, **kwargs)

    # Paralelize tweets deletion
    q = gevent.queue.JoinableQueue()

    def worker(oauth_client_builder):
        while True:
            status_id = q.get()
            try:
                twitter_destroy_status(oauth_client_builder, status_id)
                log.info(u"Deleted tweet {}".format(status_id))
            except TwitterResponseError:
                log.error(u"Failed to delete tweet {}, queueing again".format(status_id))
                q.put(status_id)
            finally:
                q.task_done()

    for i in range(num_workers):
         gevent.spawn(worker, oauth_client_builder)

    for status in statuses:
        q.put(status['id'])

    q.join()  # block until all tasks are done


def parse_args():
    import argparse

    parser = argparse.ArgumentParser(description=u"OAuth client")

    # URLs
    parser.add_argument('--request-token-url', required=False, default=OAUTH_REQUEST_TOKEN_URL,
                        dest='request_token_url', type=str, action='store')
    parser.add_argument('--access-token-url', required=False, default=OAUTH_ACCESS_TOKEN_URL,
                        dest='access_token_url', type=str, action='store')
    parser.add_argument('--authorize-url', required=False, default=OAUTH_AUTHORIZE_URL,
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
    parser.add_argument('--debug', dest='debug', default=False, action='store_true',
                        help=u"Show debug information")
    parser.add_argument('--quiet', dest='quiet', default=False, action='store_true',
                        help=u"Only show fatal errors")
    parser.add_argument('--num-workers', required=False, default=5,
                        dest='num_workers', type=int, action='store')


    # Twitter
    parser.add_argument('--twitter-statuses-count', default=200, action='store',
                        dest='twitter_statuses_count', type=int)
    parser.add_argument('--twitter-statuses-page', default=0, action='store',
                        dest='twitter_statuses_page', type=long)
    parser.add_argument('--twitter-delete-retweets', default=True, action='store_true',
                        dest='twitter_delete_retweets')

    parser.add_argument('twitter_screen_name', type=str, action='store')

    args = parser.parse_args()

    if args.request_token_key and not args.request_token_secret:
            parser.error(u"Missing '--request-token-secret'")

    if args.access_token_key and not args.access_token_secret:
            parser.error(u"Missing '--access-token-secret'")

    return args


if __name__ == '__main__':
    args = parse_args()

    if args.debug:
        log_level = logging.DEBUG
    elif args.quiet:
        log_level = logging.FATAL
    else:
        log_level = logging.INFO
    logging.basicConfig(level=log_level)


    log.info(u"Attempting to delete {:d} tweets from user {:s} at page {:d}" \
                .format(args.twitter_statuses_count,
                        args.twitter_screen_name,
                        args.twitter_statuses_page))

    if args.access_token_key:
        access_token_key = args.access_token_key
        access_token_secret = args.access_token_secret
    else:
        # Needlesdy do this so we only bother the user once to get the Access Token
        oauth_client = build_authorized_oauth_client(
            request_token_url=args.request_token_url,
            access_token_url=args.access_token_url,
            authorize_url=args.authorize_url,
            consumer_key=args.consumer_key,
            consumer_secret=args.consumer_secret,
            request_token_key=args.request_token_key,
            request_token_secret=args.request_token_secret)
        access_token_key = oauth_client.token.key
        access_token_secret = oauth_client.token.secret

    def oauth_client_builder():
        return build_authorized_oauth_client(
            request_token_url=args.request_token_url,
            access_token_url=args.access_token_url,
            authorize_url=args.authorize_url,
            consumer_key=args.consumer_key,
            consumer_secret=args.consumer_secret,
            access_token_key=access_token_key,
            access_token_secret=access_token_secret)

    delete_tweets_page(oauth_client_builder,
                       screen_name=args.twitter_screen_name,
                       include_rts=args.twitter_delete_retweets,
                       page=args.twitter_statuses_page,
                       count=args.twitter_statuses_count,
                       num_workers=args.num_workers)
