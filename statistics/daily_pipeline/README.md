# Daily aggregate statistics


## Daily article counts per outlet
To keep track of whether our news article scrapers are performing, an additional app is added to [our research dashboard](https://gendergaptracker.research.sfu.ca/). We plot daily counts of articles for all news outlets in English and French over a given time period. To do this, we run a daily aggregator script that counts the number of sources and articles for each outlet each day, and write this to the `mediaDaily` collection on the DB. Following this, the charts on the dashboard query the data from the last 180 days, so that we can see if there is an abrupt decline in daily article counts per outlet over a sustained period -- this could be an indication that a particular scraper is out of date and that we need to more closely inspect its source code.

#### Run the daily article/source aggregator script
This script aggregates the number of articles and sources per gender, per outlet, and writes them to the `mediaDaily` collection in the database. By default, this runs over all articles published within the last 180 days (6 months). Alternately, a custom date range over which the daily counts need to be performed can be specified as follows.

```sh
cd daily_pipeline
python3 media_daily.py --begin_date 2021-10-01 --end_date 2021-10-31
```
