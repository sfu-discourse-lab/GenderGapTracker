# This program collects metadata and full text of articles from Different media outlets.
# It is the first major step in a three step pipeline to support an Informed Opinions project that is meant
# to track and report on the representation of experts by gender in media outlets.
# Date created: 2018/07/25
import re
import json
import sys
import pprint
import argparse
import logging
import newspaper
import datetime
import code
import signal
import traceback
import tldextract
import itertools
from util import *
from config import *
from bs4 import BeautifulSoup
from pymongo import MongoClient
from logging import StreamHandler
from urllib.parse import urlparse
from newspaper import ArticleException
log = logging.getLogger('mediaCollectorsLogger')
log.setLevel(logging.INFO)


# This allows adding new articles and comparing them
#  For the urls comparison we wipe the scheme ignoring differences between http/https
class CollectorParam:

    task = None
    url = None
    fields = None
    priority = 100
    prefix = ""

    def __init__(self, task, priority, url, fields):
        self.task = task
        self.url = url
        self.fields = fields
        self.priority = priority

    def __hash__(self):
        url = CollectorParam.strip_scheme(self.url)
        return url.__hash__()

    def __eq__(self, other):
        url = CollectorParam.strip_scheme(self.url)
        other_url = CollectorParam.strip_scheme(other.url)
        return url.__eq__(other_url) and self.task.__eq__(other.task)

    def __gt__(self, other):
        return self.priority.__gt__(other.priority)

    @staticmethod
    def strip_scheme(url):
        parsed = urlparse(url)
        scheme = "%s://" % parsed.scheme
        return parsed.geturl().replace(scheme, '', 1)


# The are the high level tasks the every collector has tp implement
class Collector:

    level = 0
    added_urls = set()
    domain = ""
    __connection = MongoClient(MONGODB_HOST, MONGODB_PORT, **MONGO_ARGS)
    __mediaCollection = __connection[DBS_NAME][COLLECTION_NAME]
    __ldjsonCollection = __connection[DBS_NAME]["mediaLDjson"]
    __mediaInvalidCollection = __connection[DBS_NAME][COLLECTION_INVALID_NAME]
    prefix = ""
    downloaded = 0
    # Because the scrapper was being blocked I mimic the browser parameters and it stopped
    _headers = {
        "scheme": "https",
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
        "accept-encoding": "gzip, deflate, br",
        "accept-language": "en-US,en;q=0.9,pt;q=0.8,fr;q=0.7",
        "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/67.0.3396.62 Safari/537.36",
    }

    def __init__(self, outlet, initial_url, prefix="", **kwargs):
        self.outlet = outlet
        self.initial_url = initial_url
        ext_ret = tldextract.extract(initial_url)
        self.prefix = prefix
        self.domain = ext_ret.domain + "." + ext_ret.suffix
        self.args = {"memoize_articles": False,
                     "MIN_SENT_COUNT": 5,
                     "MIN_WORD_COUNT": 100,
                     "browser_user_agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko)",
                     "headers": self._headers}

        self.args.update(kwargs)

        # self.__config.verbose = True

    def get_name(self):
        return self.outlet

    def initial_urls(self):
        self.added_urls.add(self.initial_url)
        return [self.initial_url]

    def process(self, collector_param):
        log.info("Process: %s", collector_param.url)
        articles = newspaper.build(self.get_url_w_prefix(collector_param.url), **self.args)

        categories = articles.categories
        article_2_search = set()

        if self.level == 0:
            for category in categories:
                url = self.clean_url(category.url)
                if url not in self.added_urls and self.url_check(url):
                    article_2_search.add(CollectorParam(self.process, 3, url, dict()))
                    article_2_search.add(CollectorParam(self.process_article, 2, url, dict()))
                    self.added_urls.add(url)
                    log.info("Explore category Url: %s", url)
                else:
                    log.debug("Not adding category: %s already present", url)
            self.level = 1

        rejected = 0
        for article in articles.articles:
            url = self.clean_url(article.url)
            if url not in self.added_urls and self.url_check(url):
                article_2_search.add(CollectorParam(self.process_article, 2, url, dict()))
                self.added_urls.add(url)
            else:
                rejected += 1
                log.debug("Rejecting: %s ", url)
                self.added_urls.add(url)
        return article_2_search

    def process_article(self, collector_param):
        log.info("Process Article: " + collector_param.url)
        log.debug("Process Article: " + self.get_url_w_prefix(collector_param.url))

        if(self.__mediaInvalidCollection.find({"url": {"$in": self.ret_urls_2_search(collector_param.url)},
                                               "outlet": self.outlet}).count() == 0 and
                self.__mediaCollection.find({"url": {"$in": self.ret_urls_2_search(collector_param.url)},
                                             "outlet": self.outlet}).count() == 0):

            article = newspaper.Article(self.get_url_w_prefix(collector_param.url), **self.args)

            try:
                article.download()
                article.parse()
                self.downloaded += 1
                if article.is_valid_body():
                    collector_param.fields["title"] = article.title
                    if article.publish_date:
                        collector_param.fields["publishedAt"] = article.publish_date
                    else:
                        raise Exception("Article publish date not found")

                    collector_param.fields['authors'] = article.authors
                    log.debug("Title: " + collector_param.fields['title'] + " Author: " + str(collector_param.fields['authors']))
                    log.info("Title: " + collector_param.fields['title'] + " publishedAt: " + str(collector_param.fields['publishedAt']))

                    collector_param.fields.update({
                        "outlet": self.outlet,
                        "url": self.clean_url(collector_param.url),
                        "body": article.text,
                        "bodyRaw": article.html,
                    })
                    return [CollectorParam(self.add_to_collection, 1, None, collector_param.fields)]
                else:
                    log.info("Rejected invalid body: %s", collector_param.url)
                    # log.info("Body: %s", article.text)
                    data = {"outlet": self.outlet, "url": collector_param.url}
                    self.__mediaInvalidCollection.update_one(data, {'$setOnInsert': data}, upsert=True)
                    return "Invalid Body"
            except ArticleException as e:

                log.info("Rejected invalid: %s - %s", collector_param.url, e)
                data = {"outlet": self.outlet, "url": collector_param.url}
                self.__mediaInvalidCollection.update_one(data, {'$setOnInsert': data}, upsert=True)
                return "Invalid"
        else:
            log.info("URL found in the database")
            return "URL Present"

    def add_to_collection(self, collector_param):
        fields = collector_param.fields
        log.info("Add to Collection Date: %s: - Url: %s ",  fields['publishedAt'], fields['url'])

        printable = dict(fields)
        del printable['body']
        del printable['bodyRaw']
        log.debug("Fields less bodies: " + pprint.pformat(printable))
        # log.info("Fields: " + pprint.pformat(fields))
        # Remove trailling slash

        header = {"url": fields['url']}
        print(fields['url'])
        collector_param.finished = True
        try:
            fields["lastModified"] = datetime.now()
            fields["lastModifier"] = "mediaCollectors"
            inserted = self.__mediaCollection.update_one(header, {'$setOnInsert': fields}, upsert=True)

            parsed = BeautifulSoup(fields["bodyRaw"], 'html.parser')

            for script in parsed.find_all('script', {'type': 'application/ld+json'}):
                if script.text:
                    ld_data = json.loads(script.text, strict=False)
                    ld_data['article_id'] = inserted.upserted_id
                    log.info("Adding ldjson info")
                    self.__ldjsonCollection.insert_one(ld_data)

            for script in parsed.find_all('script', {'id': 'page-data'}):
                if script.text:
                    ld_data = json.loads(script.text, strict=False)
                    ld_data['article_id'] = inserted.upserted_id
                    log.info("Adding ldjson info")
                    self.__ldjsonCollection.insert_one(ld_data)

            return "Inserted"
        except Exception as error:
            raise Exception("Error when inserting: " + str(fields) + " Exception: ", error)

    def url_check(self, url):
        ext_ret = tldextract.extract(url)
        url_domain = ext_ret.domain + "." + ext_ret.suffix

        if url_domain != self.domain:
            return False
        if "ban_subdomains" in self.args:
            for ban_subdomains in self.args["ban_subdomains"]:
                sub_domain = tldextract.extract(ban_subdomains).subdomain
                if sub_domain == ext_ret.subdomain:
                    log.info("Banned subdomain: " + url)
                    return False

        return True

    # These are heuristic that mainly avoid same url in two different forms when comparing URLs
    def ret_urls_2_search(self, url):
        urls_out = set()
        urls_out.add(url)

        if url.startswith("https://"):
            ret = re.sub("^https://", "", url)
            urls_out.add("http://" + ret)
            if ret.startswith("www"):
                ret = re.sub("^www.", "", ret)
                urls_out.add("https://" + ret)
                urls_out.add("http://" + ret)
            else:
                urls_out.add("https://www." + ret)
                urls_out.add("http://www." + ret)

        elif url.startswith("http://"):
            ret = re.sub("^http://", "", url)
            urls_out.add("https://" + ret)
            if ret.startswith("www"):
                ret = re.sub("^www.", "", ret)
                urls_out.add("https://" + ret)
                urls_out.add("http://" + ret)
            else:
                urls_out.add("https://www." + ret)
                urls_out.add("http://www." + ret)

        ext_ret = tldextract.extract(url)
        path = urlparse(url).path
        url_domain_path = ext_ret.domain + "." + ext_ret.suffix + path
        # print(url_domain_path)
        urls_out.add("https://" + url_domain_path)
        urls_out.add("http://" + url_domain_path)

        return list(urls_out)

    def clean_url(self, url):
        # Remove get parameters
        parsed = urlparse(url)
        url = parsed.scheme + "://" + parsed.netloc + parsed.path
        # Remove URL prefix
        url_clean_regex = re.compile(self.prefix)
        url = url_clean_regex.sub("", url)
        # Remove trailling slash
        return re.sub("\/$", "", url)

    def get_url_w_prefix(self, url):
        if self.prefix:
            if self.prefix not in url:
                parsed = urlparse(url)
                return parsed.scheme + "://" + self.prefix + parsed.netloc + parsed.path
        else:
            return url


def collect_pages(media_collector):

    log.info("Collecting pages for: " + media_collector.get_name())

    collector_params = set([CollectorParam(media_collector.process, 3, url, dict())
                            for url in media_collector.initial_urls()])

    queue = PrioritySet()
    for collector_param in collector_params:
        queue.add(collector_param)

    result = []
    while len(queue) > 0:
        try:
            log.info("Len queue: %s Len set: %s", len(queue), len(mediaCollector.added_urls))
            collector_param = queue.get()
            ret = collector_param.task(collector_param)
            if not isinstance(ret, str):
                [queue.add(item) for item in ret]
            else:
                result.append(ret)
        except Exception:
            log.exception("Error processing: %s Exception: ", collector_param)
            result.append("Error")

    log.error("Finished %s! Inserted: %s - Updated: %s - Error: %s - Invalid Body: %s - "
              "URL Present: %s - Downloaded: %s",
              media_collector.get_name(),
              len(list(filter(lambda r: r == "Inserted", result))),
              len(list(filter(lambda r: r == "Updated", result))),
              len(list(filter(lambda r: r == "Error", result))),
              len(list(filter(lambda r: r == "Invalid Body", result))),
              len(list(filter(lambda r: r == "URL Present", result))),
              media_collector.downloaded)


def debug(sig, frame):
    """Interrupt running process, and provide a python prompt for
    interactive debugging."""
    d={'_frame':frame}         # Allow access to frame object.
    d.update(frame.f_globals)  # Unless shadowed by global
    d.update(frame.f_locals)

    i = code.InteractiveConsole(d)
    message  = "Signal received : entering python shell.\nTraceback:\n"
    message += ''.join(traceback.format_stack(frame))
    i.interact(message)


def listen():
    signal.signal(signal.SIGUSR1, debug)  # Register handler


def log_setup(modules):

    format = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    rotateHandler = CustomTimedRotatingFileHandler(LOGS_DIR + "-".join(modules), when="midnight")
    rotateHandler.suffix += ".log"
    rotateHandler.setFormatter(format)

    buffSMTPHandler = BufferingSMTPHandler(EMAIL_SERVER, EMAIL, EMAIL_DESTINATION, "-".join(modules),
                                         credentials=(EMAIL_ACCOUNT, EMAIL_PASSWORD))

    buffSMTPHandler.setFormatter(format)
    buffSMTPHandler.level = logging.ERROR
    log.addHandler(rotateHandler)
    stream = StreamHandler(sys.stdout)
    # stream.level = logging.DEBUG
    log.addHandler(StreamHandler(sys.stdout))
    # log.addHandler(buffSMTPHandler)

    return rotateHandler, buffSMTPHandler


def global_news_feed_extractor(parser, category):

    feed_elements = parser.getElementsByTag(category.doc, tag="li")
    links = []
    for feed in feed_elements:
        tmp_links = feed.findall('a')

        for l in tmp_links:
            if 'href' in l.attrib:
                links.append(l.attrib['href'])

    return links


def cbc_news_feed_extractor(parser, category):

    parsed = BeautifulSoup(category.html, 'html.parser')
    elements = parsed.find_all("td", {"class": "content"})
    links = []
    for element in elements:
        links.append(element.find('a').get('href'))

    return links


def la_presse_feed_extractor(parser, category):

    parsed = BeautifulSoup(category.html, 'html.parser')
    article_list = parsed.findAll("input", {"type": "text"})

    links = []
    for article in article_list:
        link = article.get('value')
        if link:
            links.append(link)

    return links


def journal_de_montreal_feed_extractor(parser, category):

    parsed = BeautifulSoup(category.html, 'html.parser')

    urlsTags = [ulTag.find_all("a") for ulTag in parsed.find_all("ul", {"class": "flux_rss"})]
    urlsTags = list(itertools.chain(*urlsTags))

    links = []
    for link_tag in urlsTags:
        if link_tag is not None:
            link = link_tag.get('href')
            if link:
                links.append(link)

    return links


def radio_canada_feed_extractor(parser, category):

    parsed = BeautifulSoup(category.html, 'html.parser')

    links = []
    for link_tag in parsed.findAll("a", {"class": "e-external-link alternative-link text-svg-icon"}):
        if link_tag is not None:
            link = link_tag.get('href')
            if link:
                links.append(link)

    return links


if __name__ == "__main__":

    mediaCollectors = [Collector("Global News", "https://globalnews.ca",
                                 feeds_urls=['/pages/feeds'],
                                 feed_url_extractor=global_news_feed_extractor),
                       Collector("CTV News", "https://www.ctvnews.ca"),
                       Collector("The Star", "https://www.thestar.com"),
                       Collector("Huffington Post", "https://www.huffingtonpost.ca",
                                 ban_subdomains=["quebec.huffingtonpost.ca", "m.quebec.huffingtonpost.ca"]),
                       Collector("CBC News", "https://www.cbc.ca",
                                 feeds_urls=['/rss'],
                                 feed_url_extractor=cbc_news_feed_extractor),
                       Collector("National Post", "https://nationalpost.com"),
                       Collector("The Globe And Mail", "https://www.theglobeandmail.com",
                                 prefix="shari@informedopinions.org:imUP2date8@"),
                       Collector("TVA News", "http://tva.canoe.ca/", language="fr"),
                       Collector("Radio Canada", "http://ici.radio-canada.ca", language="fr",
                                 feeds_urls=["/mesAbonnements/rss"],
                                 feed_url_extractor=radio_canada_feed_extractor),
                       Collector("La Presse", "http://www.lapresse.ca", language="fr",
                                 feeds_urls=["/rss.php"],
                                 feed_url_extractor=la_presse_feed_extractor),
                       Collector("Journal De Montreal", "https://www.journaldemontreal.com", language="fr",
                                 feed_url_extractor=journal_de_montreal_feed_extractor),
                       Collector("Le Droit", "https://www.ledroit.com", language="fr"),
                       Collector("Le Devoir", "https://www.ledevoir.com/", language="fr")]

    parser = argparse.ArgumentParser(description="Collect media news from different outlets")
    parser.add_argument("modules",
                        type=str,
                        nargs="+",
                        help="Values: " + ", ".join(map(lambda m: m.get_name(), mediaCollectors)))

    args = parser.parse_args()
    rotateHandler, buffSMTPHandler = log_setup(args.modules)

    log.info("Args: " + str(args))
    log.info("Calling listen")
    listen()

    for mediaCollector in mediaCollectors:
        if mediaCollector.get_name().lower() in [module.lower() for module in args.modules]:
            collect_pages(mediaCollector)



