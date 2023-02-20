# Statistics

This folder contains scripts to programmatically collect and display statistics for tracking purposes or for summarizing trends related to the GGT and RdP.

## Installation

**Python 3.6+ is required** for all the scripts in this directory. First, install the required dependencies in a virtual environment via `requirements.txt`.

```
python3 -m venv venv
source venv/bin/activate
python3 -m pip install -U pip wheel
python3 -m pip install -r requirements.txt
```

---

## 1. Running database queries

Running repetitive queries manually on the MongoDB database using a GUI client like Studio 3T can be time-consuming and tedious. For retrieving fine-grained stats or aggregations over weeks or months (rather than years), each query's run time is comparable to the time taken by a human to manually click through the actions on the database GUI. Due to the number of such queries that need to be run sequentially, it makes sense to automate their execution using a Python script, as shown below.

### Database tunnel
To run the query script locally, a database tunnel can be used. To do this, forward the ssh connection to the virtual machine that hosts the database (in this case `vm12`) to serve results on `localhost` through port 27017.

```
ssh vm12 -f -N -L 27017:localhost:27017
```
Alternatively, if a tunnel cannot be set up, the query script can be directly run on the database VM instance.


## Aggregation query runner
The script `run.py` contains the logic for running commonly used aggregation queries on the database. 

### Usage
The script uses optional command line arguments to call specific queries such gender stats, or source counts based on outlet, etc. The start date, end date and outlets to be considered by the query are some of the arguments specified by the user.

A full list of optional arguments for the script is given below.

```
python3 run.py --help

optional arguments:
  -h, --help            show this help message and exit
  --begin_date BEGIN_DATE
                        Start date in the format YYYY-MM-DD
  --end_date_date END_DATE   End date in the format YYYY-MM-DD
  --outlets OUTLETS     Comma-separated list of news outlets to consider in
                        query scope
  --limit LIMIT         Number of results to limit to
  --sort SORT           Sort results in ascending or descending order
  --db_stats            Run query to calculate overall gender stats (sources,
                        people, authors)
  --outlet_stats        Run query to calculate gender stats (sources, people,
                        authors) per outlet
  --top_sources_female  Run query to calculate top 100 female sources
  --top_sources_male    Run query to calculate top 100 male sources
  --top_sources_all     Run query to calculate top 100 sources (male or
                        female)
  --female_author_sources
                        Run query to cross-tabulate female author sources vs.
                        source gender counts
  --male_author_sources
                        Run query to cross-tabulate male author sources vs.
                        source gender counts
  --mixed_author_sources
                        Run query to cross-tabulate both gender (male &
                        female) author sources vs. source gender counts
  --unknown_author_sources
                        Run query to cross-tabulate unknown author sources vs.
                        source gender counts
```

### Example commands

#### All outlets
To extract per-outlet gender stats *as well as* top female sources in a given month in a single run, use the below command. Not specifying the `--outlet` flag considers all 7 English-language outlets by default.

```
python3 run.py --begin_date 2020-04-01 --end_date 2020-04-30 --outlet_stats --top_sources_female
```

#### Limit to specific outlet and top-N sources
To limit to just the top 50 sources for just 3 outlets - '*The Star, CBC News, National Post*' - specify these outlet names **as a comma-separated list**. Since the outlet names contain spaces, each name must be enclosed in double quotes.

```
python3 run.py --begin_date 2020-04-01 --end_date 2020-04-30 --outlet_stats --top_sources_female --limit 50 --outlets "The Star","National Post","CBC News"
```

#### Sort top-N sources in ascending order (i.e. bottom-M results)
The order of sorting can be reversed by using the `--sort` argument as shown below. Here, "ascending" means that we are calculating the counts of all sources (male or female), and sorting from lowest to highest counts. This query is used when we want to see who are the *least* quoted people in a given time period.

```
python3 run.py --begin_date 2020-04-01 --end_date 2020-04-30 --top_sources_female --sort asc --limit 100
```

#### Run a large number of queries in batch mode
To run a series of queries over different periods of time, create a shell script `execute.sh` with individual query parameters.

```bash
#!/usr/bin/sh

python3 run.py --begin_date 2018-10-01 --end_date 2018-10-31 --top_sources_female --top_sources_male --limit 100 --sort desc
python3 run.py --begin_date 2018-11-01 --end_date 2018-11-30 --top_sources_female --top_sources_male --limit 100 --sort desc
python3 run.py --begin_date 2018-12-01 --end_date 2018-12-31 --top_sources_female --top_sources_male --limit 100 --sort desc
...
...
```
Because individual queries can take a while to run on the database, it makes sense to run the script using bash and nohup as follows. Running this way means the terminal window can be closed while the script runs in the background.

```
nohup bash execute.sh
```

### Extending the query list
The current list of aggregation queries are stored in `queries.py`, and include many of the commonly used queries that are regularly used on the database.

* DB overall stats
* Source, mention and author genders grouped by outlet
* Source counts per gender, grouped by outlet
* Source counts per gender based on author gender, grouped by outlet


#### 1. Update `queries.py`
Any additional queries in the future can be added to the file `queries.py`. All that needs to be ensured is that the query is defined in a method that returns a list containing a valid Python dictionary. An example is shown below.

```python
def db_stats(args: Dict[str, Any]) -> List[object]:
    """Returns the overall counts of articles, quotes, sources, people and
       authors in the database.
    """
    query = [
        {
            "$match": {
                "body": {"$ne": ""},
                "quotesUpdated": {"$exists": True},
                "outlet": {"$in": args['outlets']},
                "publishedAt": {"$gte": args['start'], "$lt": args['end'] + timedelta(days=1)}
            }
        },
        {
            "$group": {
                "_id": "null",
                "totalArticles": {"$sum": 1},
                "totalQuotes": {"$sum": "$quoteCount"},
                "peopleFemaleCount": {"$sum": "$peopleFemaleCount"},
                "peopleMaleCount": {"$sum": "$peopleMaleCount"},
                "peopleUnknownCount": {"$sum": "$peopleUnknownCount"},
                "sourcesFemaleCount": {"$sum": "$sourcesFemaleCount"}, 
                "sourcesMaleCount": {"$sum": "$sourcesMaleCount"}, 
                "sourcesUnknownCount": {"$sum": "$sourcesUnknownCount"},
                "authorsFemaleCount": {"$sum": "$authorsFemaleCount"},
                "authorsMaleCount": {"$sum": "$authorsMaleCount"},
                "authorsUnknownCount": {"$sum": "$authorsUnknownCount"}
            }
        }
    ]
    return query
```
Any relevant query parameters can be passed via the argument dict, `args` as shown.


#### 2. Update argument parser in `run.py` with the new method name
The argument parser in `run.py` defines optional boolean arguments. Each time a new query is added to `queries.py`, an argument with the same name as the method must be added to the argument parser. An example is shown below.

```python
parser.add_argument("--db_stats", action='store_true', help="Run query to calculate overall gender stats (sources, people, authors)")
```
This allows the user to request the new defined method containing the relevant query from the command line.
