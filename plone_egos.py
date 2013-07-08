import pprint
import os
import glob
from jinja2 import Environment, FileSystemLoader
from ConfigParser import SafeConfigParser
from twython import Twython, TwythonError


TEMPLATE_DIR = '/Users/phong/PyClass/feb17_hashtag/templates'
WEB_DIR = '/Users/phong/PyClass/feb17_hashtag/www'

HTML_PAGE_STARTS_WITH = 'hashtag_page'
FILE_SUFFIX = '.html'

TWEETS_PER_PAGE = 10


# debug aid
def print_tweets_to_screen(tweets):
    pp = pprint.PrettyPrinter(indent=2)
    pp.pprint(tweets)

def print_tweets_to_file(tweets, file_name):
    with open(file_name, 'wb') as f:
        pp = pprint.PrettyPrinter(indent=2)
        f.write(pp.pformat(tweets))

# ---
# custom filters
def generate_file_name(num):
    if num == 1:
        return os.path.join(WEB_DIR, "index.html")
    else:
        return os.path.join(WEB_DIR, "{0}{1:03d}{2}".format(HTML_PAGE_STARTS_WITH,
            num, FILE_SUFFIX))

def resurrect_links(tweet_text, links):
    # links is a list of dict(s) containing info about links in the tweet
    if links:
        # if there are multiple links then sort in reverse order of indices
        if len(links) > 1:
            links.sort(key=lambda link:link['indices'], reverse=True)

        # resurrect each links, starting from the end of each tweet text moving
        # from right to left
        for link in links:
            start, end = link['indices']
            tweet_text = tweet_text[:start] + "<a href=\"" + link['resource_url'] + "\"" + ">" \
                + link['display_url'] + "</a>" + tweet_text[end:]
        return tweet_text

# ---
# main defs
def remove_files(directory, suffix):
    # use glob for Unix style wildcard path expansion for full path
    files_to_remove = glob.glob("{0}/{1}{2}".format(WEB_DIR, "*", suffix))
    print "files to remove: {0}".format(files_to_remove)
    for f in files_to_remove:
        os.remove(f)

def process_tweets(tweet, tweet_list):
    print "tweet id: {0}".format(tweet['id'])
    print "user: {0}".format(tweet['user']['name'].encode('utf-8'))
    print "tweeted: {0}\n".format(tweet['text'].encode('utf-8'))

    # if a retweet don't add it to the list
    if tweet['text'][:2] == 'RT':
        return

    # create our own tweet object
    each_tweet = {}
    each_tweet['text'] = tweet['text']
    each_tweet['screen_name'] = tweet['user']['screen_name']

    each_tweet['name'] = tweet['user']['name']
    each_tweet['profile_image'] = tweet['user']['profile_image_url']
    each_tweet['id'] = tweet['id']
    each_tweet['created_at'] = tweet['created_at'][5:12] + '--' + tweet['created_at'][16:25]

    # list contains link info dicts
    each_tweet['links'] = []

    # add any media link, note that twitter only supports one media per tweet
    if 'media' in tweet['entities']:
        each_tweet['media_url'] = tweet['entities']['media'][0]['media_url']
        link = {}
        link['display_url'] = tweet['entities']['media'][0]['url']
        link['resource_url'] = tweet['entities']['media'][0]['media_url']
        link['indices'] = tweet['entities']['media'][0]['indices']
        each_tweet['links'].append(link)

    # add links from the url section
    if tweet['entities']['urls']:
        link = {}
        for url in tweet['entities']['urls']:
            link['display_url'] = url['url']
            link['resource_url'] = url['expanded_url']
            link['indices'] = url['indices']
            each_tweet['links'].append(link)

    # add tweet object to tweet list
    tweet_list.append(each_tweet)

def get_tweets(hashtag):
    print "Retrieving tweets..."

    # get twitter oAuth credentials
    parser = SafeConfigParser()
    parser.read('hashtag.ini')

    app_key = parser.get('twitter', 'consumer_key')
    app_secret = parser.get('twitter', 'consumer_secret')
    oauth_token = parser.get('twitter', 'access_token')
    oauth_token_secret = parser.get('twitter', 'access_token_secret')
    max_request_per_execution = int(parser.get('twitter',
        'max_request_per_execution'))

    # initialize a Twitter handle
    twitter = Twython(app_key, app_secret, oauth_token, oauth_token_secret)

    # set initial value for max_id to something other than None
    next_max_id = None
    tweet_list = []
    number_of_loops = 0

    # while loop and half to get all search result pages
    # check for break out condition at bottom of the loop
    while True:
        number_of_loops += 1
        print "before sending request, max_id is: {0}".format(next_max_id)
        try:
            if next_max_id is None:
                print "sending request without max_id"
                search_results = twitter.search(q=hashtag, count=100)
            else:
                print "sending request with max_id"
                search_results = twitter.search(q=hashtag, count=100,
                    max_id=next_max_id)
        except TwythonError as e:
            print e

        # process tweets
        for tweet in search_results['statuses']:
            process_tweets(tweet, tweet_list)

        # determine if more pages to request
        # parse max_id if present, else set next_max_id to None
        if 'next_results' in search_results['search_metadata']:
            next_results_field = search_results['search_metadata']['next_results']
            print "response has next_results field: {0}".format(next_results_field)
            next_results_list = (next_results_field.encode('utf-8')).split('&')
            # first element of the next results field and slice off
            # the ?max_id=
            next_max_id = next_results_list[0][8:]
            print "this batch's max id: {0}\n".format(next_max_id)
        else:
            print "next max_id is None!"
            next_max_id = None

        # condition for breaking while loop
        if (next_max_id is None) or (number_of_loops >
            max_request_per_execution):
            print "breaking out loop, number of loops: {0}".format(number_of_loops)
            break

    return tweet_list

def split_tweets_into_pages(tweets, tweets_per_page):
    return [tweets[i:i+tweets_per_page] for i in range(0,
        len(tweets), tweets_per_page)]

def prepare_html_pages(tweets, tweets_per_page, directory):
    print "Generating html pages..."

    # tell jinja where to find the template
    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
    # register custom filter
    env.filters['generate_file_name'] = generate_file_name
    env.filters['resurrect_links'] = resurrect_links
    html_template = env.get_template('simple-basic.html')

    # transform tweets list into list of lists
    # each sublist contains tweets_per_page number of tweets
    list_of_tweet_pages = split_tweets_into_pages(tweets, tweets_per_page)

    # generate file names, page links, and render pages
    # web pages starts with index 1 (e.g. hashtag_page001.html) so adjust
    # zero-based index accordingly
    for num, page in enumerate(list_of_tweet_pages):
        page_file_name = generate_file_name(num+1)
        print "page file name is: {0}".format(page_file_name)
        html_page = html_template.render(tweets=page,
            num_of_pages=len(list_of_tweet_pages),
            current_page=(num+1))

        # save to directory
        print "filename: %s" % ( page_file_name )
        with open(page_file_name, 'wb') as f:
            f.write(html_page.encode('utf-8'))

def create_hashtag_html_pages(hashtag):
    remove_files(WEB_DIR, FILE_SUFFIX)
    tweets = get_tweets(hashtag)

    #for tweet in tweets:
    #   print "tweet id: {0}".format(tweet['id'])
    #  print "user: {0}".format(tweet['name'].encode('utf-8'))
    # print "tweeted: {0}\n".format(tweet['text'].encode('utf-8'))

    print "harvested {0} texts!".format(len(tweets))

    prepare_html_pages(tweets, TWEETS_PER_PAGE, WEB_DIR)
    print "Success!"

if __name__ == '__main__':
    create_hashtag_html_pages("brompton bike")
