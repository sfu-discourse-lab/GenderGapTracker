# Monthly aggregate statistics

For [our research dashboard](https://gendergaptracker.research.sfu.ca/), we aggregate our results on a monthly basis. This is primarily for us to study trends in our topic models each month, as well as to analyze the top quoted men and women over time.

Calculate the top 50 quoted men and women for a particular month by specifying the month and year as follows:

```sh
cd monthly_aggregate
# Calculate top 50 male & female sources for all outlets for November and December 2020
python3 monthly_top_sources.py --year 2020 --month 11
python3 monthly_top_sources.py --year 2020 --month 12
```

Similarly, we can calculate the top 50 quoted men and women each month to study the top quoted people's quote counts as a time series. We limit the calculation to just the top 50 for querying-efficiency reasons (otherwise the time series lookup can become inefficient). Each month's calculation is run one at a time, sequentially, as follows.

```sh
cd monthly_aggregate
# Calculate the quote counts for each of the top 50 male & female sources for all outlets for April, May and June 2020
python3 monthly_top_sources_timeseries.py --year 2020 --month 4
python3 monthly_top_sources_timeseries.py --year 2020 --month 5
python3 monthly_top_sources_timeseries.py --year 2020 --month 6
```
