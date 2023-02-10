# This module aggregates different functions used for scrapping news RSS feeds websites
# Date created: 2018/07/19
import re
import os
import heapq
import smtplib
import logging as log
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler, BufferingHandler


def str_or_empty_str(tag):
    return "" if tag is None or tag.string is None else tag.string


def text_or_empty_str(tag):
    return "" if tag is None or tag.text is None else tag.text


def clean_text(text):
    # Regex to remove non printable chars
    return re.sub(r"[\x00-\x1F]+", " ", text).rstrip().strip().lower()


def enable_debug_http():
    try:
        import http.client as http_client
    except ImportError:
        # Python 2
        import httplib as http_client
    http_client.HTTPConnection.debuglevel = 1

    # DEBUG
    log.basicConfig()
    log.getLogger().setLevel(log.DEBUG)
    requests_log = log.getLogger("requests.packages.urllib3")
    requests_log.setLevel(log.DEBUG)
    requests_log.propagate = True


def conv_str2date(strDate):

    strDate = (
        strDate.replace("GMT", "")
        .replace("-0400", "")
        .replace("EDT", "")
        .replace("EST", "")
        .replace("+0000", "")
        .replace("-0300", "")
        .replace("-0700", "")
        .replace("-0600", "")
        .replace("-0500", "")
        .replace("-0001 ", "")
        .replace(".000", "")
        .strip()
    )
    try:
        try:
            convDate = datetime.strptime(strDate, "%a, %d %b %Y %H:%M:%S")
        except ValueError:
            try:
                convDate = datetime.strptime(strDate, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                convDate = datetime.strptime(strDate, "%d %b %Y %H:%M:%S")

        # log.info("Converted: %s", convDate)
    except Exception as ex:
        log.exception("Exception: %s", ex)
        convDate = datetime.utcnow()

    return convDate


# Partially Extracted from: https://gist.github.com/anonymous/1379446
class BufferingSMTPHandler(BufferingHandler):
    def __init__(self, mailhost, fromaddr, toaddrs, subject, capacity=1024 * 10, credentials=None):

        BufferingHandler.__init__(self, capacity)
        self.mailhost = mailhost
        self.mailport = None
        self.fromaddr = fromaddr
        self.toaddrs = toaddrs
        self.subject = subject
        self.credentials = credentials

    def flush(self):
        if len(self.buffer) > 0:
            try:
                smtp = smtplib.SMTP_SSL(self.mailhost, 465)
                smtp.ehlo()
                smtp.login(self.credentials[0], self.credentials[1])
                body = ""
                for record in self.buffer:
                    s = self.format(record)
                    body += s + "\n"

                msg = "From: %s\nSubject: %s\n%s" % (self.fromaddr, self.subject, body)

                smtp.sendmail(self.fromaddr, self.toaddrs, msg.encode("utf-8"))
                smtp.quit()
            except:
                self.handleError(None)  # no particular record
            self.buffer = []

    def close(self):
        self.flush()


def get_filename(filename):
    # Get logs directory
    log_directory = os.path.split(filename)[0]

    # Get file extension (also it's a suffix's value (i.e. ".20181231")) without dot
    date = os.path.splitext(filename)[0]
    # date = os.path.splitext(tmp)[1][1:]

    # Create new file name
    filename = os.path.join(log_directory, date)

    # I don't want to add index if only one log file will exists for date
    if not os.path.exists("{}.log".format(filename)):
        return "{}.log".format(filename)

    # Create new file name with index
    index = 0
    f = "{}.{}.log".format(filename, index)
    while os.path.exists(f):
        index += 1
        f = "{}.{}.log".format(filename, index)
    return f


class CustomTimedRotatingFileHandler(TimedRotatingFileHandler):
    def __init__(
        self,
        filename,
        when="S",
        interval=1,
        backupCount=20,
        encoding=None,
        delay=False,
        utc=False,
        atTime=None,
    ):
        TimedRotatingFileHandler.__init__(
            self, filename, when, interval, backupCount, encoding, delay, utc, atTime
        )
        self.namer = get_filename

    def doRollover(self):

        TimedRotatingFileHandler.doRollover(self)

        if os.stat(self.baseFilename).st_size <= 0:
            os.remove(self.baseFilename)


class PrioritySet(object):
    def __init__(self):
        self.heap = []

    def add(self, d):
        heapq.heappush(self.heap, (d.priority, d))

    def get(self):
        pri, d = heapq.heappop(self.heap)
        return d

    def __len__(self):
        return len(self.heap)
