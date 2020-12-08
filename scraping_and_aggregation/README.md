# Scraping and aggregation
This section contains the code we used for scraping news article content from various Canadian outlets, as well as the code we use to extract aggregate statistics from the database. The news data processed in our NLP pipeline was downloaded from public and subscription websites of newspapers, under the ‘fair dealing’ provision in Canada’s Copyright Act. This means that the data can be made available (upon signing a license agreement) *only* for private study and/or research purposes, and **not** for commercial purposes.

## 1. Scrapers

### Installation
We use the following tools for data scraping and storage.


* MongoDB: Installation instructions [here](https://docs.mongodb.com/manual/tutorial/install-mongodb-on-ubuntu/).
* Python 3.6+: Make sure that `gcc`, `build-essential` and `python36u-devel` packages are also installed on the system.
* Newspaper3k: We use the [newspaper library](https://github.com/codelucas/newspaper) to help in the process of collecting data. However, we customized this library for our own purposes, hosted at: https://github.com/aleaugustoplus/newspaper
  * Clone this repo to the root directory of the scraper code
  * Install the dependencies for the customized newspaper library using the requirements.txt file as shown [in the repo](https://github.com/aleaugustoplus/newspaper/blob/master/requirements.txt).
  * ```pip install -r requirements.txt```


### News Sources
We currently scrape news articles from 13 different organizations' websites, in both French and English.

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

##@ Example of usage for individual scrapers

```sh
python3.6 WomenInMedia/scraper/mediaCollectors.py "Huffington Post"
python3.6 WomenInMedia/scraper/mediaCollectors.py "Journal De Montreal"
```

See the full list of valid (case-sensitive) outlet names in [`mediaCollectors.py`](https://github.com/maitetaboada/WomenInMedia/blob/master/scraper/mediaCollectors.py).


### `config.py` parameters
We use a `config.py` file to specify our MongoDB connections settings, to write the newly scraped data. Note that we specify the `readPreference` argument as `primary` here to ensure that we first read the most up-to-date items from our 3-set replica database, check for existing items with an identical URL, and only then perform the write operation (this helps avoid duplicates).

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
```

---

## 2. Aggregate statistics
We also provide code showing how we calculate aggregate statistics for the results shown in the paper, as well as for the numbers shown on our dashboards. These statistics are calculated on a daily or monthly basis, depending on the situation.

### Daily stats
We pre-compute daily statistics on the total number of male, female and unknown gender sources and people mentioned, from each outlet. These are written to a separate collection with the appropriate indexes, so that they can be efficiently retrieved for display on [our live dashboard](https://gendergaptracker.informedopinions.org/).

To generate daily statistics on the most recently processed data, run the command below:

```sh
python3 WomenInMedia/scraper/tools.py "generate_daily_collection"
```

### Monthly stats
For [our research dashboard](gendergaptracker.research.sfu.ca/), we aggregate our results on a monthly basis. This is primarily for us to study trends in our topic models each month, as well as to analyze the top quoted men and women over time.

Calculate the top 15 quoted men and women for a particular month as follows:

```sh
cd monthly_aggregate
python3 monthly_top_sources.py --begin_date 2020-12-01 --end_date 2020-12-31
```

Similarly, we can calculate the top 50 quoted men and women each month to study each person's history (in terms of the number of times they were quoted) as a time series. We limit the calculation to just the top 50 for querying-efficiency reasons.

```sh
cd monthly_aggregate
python3 monthly_top_sources_timeseries.py --begin_date 2020-04-01 --end_date 2020-04-30
```

### Custom aggregate statistics
For the reported statistics in the paper, we write custom queries submitted via `pymongo`, as shown in the `custom_aggregate` directory. Any combination of the queries, as defined in `queries.py`, can be run for a specified time period and for specified outlets as shown below.

```sh
cd custom_aggregate

# Calculate top 100 male & female sources for all outlets for October 2018
python3 run.py --begin_date 2018-10-01 --end_date 2018-10-31 --top_sources_female --top_sources_male --limit 100 --sort desc

# Calculate the per-outlet source count stats for CBC News and Huffington Post, for December 2020
python3 run.py --begin_date 2020-12-01 --end_date 2020-12-31 --outlet_stats --outlets "CBC News,Huffington Post"

# Calculate overall stats (no. of sources, people and authors per gender) for CTV News between April-November 2020
python3 run.py --begin_date 2020-04-01 --end_date 2020-11-30 --db_stats --outlets "CTV News"
```
