# Scraping

## Set up `config.py`
Set up the config settings accordingly to set up the database connection and write scraped articles.

```python
# Production config
MONGODB_HOST = ["mongo0", "mongo1", "mongo2"]
MONGODB_PORT = 27017
MONGO_ARGS = {
    "readPreference": "primary",
    "username": USERNAME,
    "password": PASSWORD,
}
DBS_NAME = 'mediaTracker'
COLLECTION_NAME = 'media'
COLLECTION_INVALID_NAME = 'mediaInvalid'
LOGS_DIR = "logs/"
EMAIL_SERVER = 'smtp.gmail.com'
EMAIL = "informed.opinions.system@gmail.com"
EMAIL_ACCOUNT = ""
EMAIL_PASSWORD = ""
EMAIL_DESTINATION = ""
```

## News Sources
We scrape news articles from 13 different organizations' websites.

#### English
1. CBC News
2. CTV News
3. Global News
4. Huffington Post
5. National Post
6. The Globe And Mail
7. The Star

#### French
1. Journal De Montreal
2. La Presse
3. Le Devoir
4. Le Droit
5. Radio Canada
6. TVA News

Each outlet's news content can be retrieved from their RSS feeds by running the required media collectors.

## Example of usage

```sh
python3.6 WomenInMedia/scraper/mediaCollectors.py "Huffington Post"
python3.6 WomenInMedia/scraper/mediaCollectors.py "Journal De Montreal"
```

See the full list of valid (case-sensitive) outlet names in [`WomenInMedia/scraper/mediaCollectors.py`](https://github.com/maitetaboada/WomenInMedia/blob/master/scraper/mediaCollectors.py).