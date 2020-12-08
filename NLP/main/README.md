# Run NLP Pipeline

This section contains the code for quote extraction and named entity gender annotation for the Gender Gap Tracker.

## Set up environment
Install Python 3.6+ and follow the below instructions to prepare the python environment.

Make sure that `gcc`, `build-essential` and `python36u-devel` packages, as well as spaCy's large language model are installed on the system.
```
virtualenv -p python3 GRIM-3
pip install -r requirements.txt
python -m spacy download en_core_web_lg
```
Activate the environment as follows:
```
source GRIM-3/bin/activate
```

All NLP scripts are in the `NLP/main` location:
```
cd GenderGapTracker/NLP/main
```

## Verify `config` parameters

The file `config.py` contains all the important parameters for database access and the NLP module.

```python
config = {
    'MONGO_ARGS': {
        'host': ['mongo0', 'mongo1', 'mongo2'],
        'port': 27017,
        'username': USERNAME,
        'password': PASSWORD,
        'authSource': 'admin',
        'readPreference': 'nearest'
    },
    'GENDER_RECOGNITION': {
        'GENDERIZE_ENABLED': False,
        'GENDERAPI_ENABLED': True,
        'GENDERAPI_TOKEN': XXXXXXXXXX,
        'HOST': 'localhost',
        'PORT': 5000
    },
    'NLP': {
        'MAX_BODY_LENGTH': 20000,
        'AUTHOR_BLOCKLIST': '<abs_path>/rules/author_blocklist.txt',
        'NAME_PATTERNS': '<abs_path>/rules/name_patterns.jsonl',
        'QUOTE_VERBS': '<abs_path>/rules/quote_verb_list.txt'
    }
}
```

The below JSON fields are used:

#### MongoDB arguments
Contains the host name, port, username and password for logging into the MongoDB production server.

#### Gender services
Contains the option flags for the 'Genderize' and 'Gender-API' external services. Note that from V4.0 onwards, we do not use Genderize anymore (our subscription has expired), so it is disabled. Only the Gender-API subscription is still active and is used as a fallback when we encounter names that aren't in our cache. The gender recognition service is hosted as a Flask service accessible via 'localhost' on port 5000.

#### NLP module
The NLP modules require static file inputs containing the blocklist words for the author names, custom name patterns (to detect non-standard `PERSON` named entities), and the quote verb allowlist. **Make sure the _absolute_ paths to these files are specified**.

To avoid memory problems in spaCy on very long articles (which could possibly crash the script), we limit the quote extraction and entity gender annotation scripts to a maximum character limit per article of 20,000.

## Concurrent processing
To speed up the CPU-intensive spaCy operations, we implement concurrent processing using the `multiprocessing` module from Python's standard library. In this approach, we divide the processing of each article's quotes/entities into batches, with each batch being processed independently on a separate process. Because the articles are completely independent of one another (no information needs to be shared between individual articles at any point during quote extraction/entity gender annotation), this is an *embarrassingly parallel* problem that is very amenable to multi-processing.

### Multi-processing vs. Multi-threading
It is important to not confuse multi-threading with multi-processing. In general, multi-threading is used to speed up I/O-bound operations (such as reading//writing information from a database), whereas multi-processing is used to speed up CPU-intensive operations (such as numerical computation or NLP tasks). 

Our initial tests showed that transferring data from MongoDB to Python (through `pymongo`) is very efficient - `pymongo` has efficient methods in place to return a huge list of document IDs that we can then iterate though efficiently. `pymongo` also returns the data in batches of generator objects (cursors), with each batch being roughly 100 documents or so in size (depending on the individual documents' size). This is *not* an I/O-intensive step, because `pymongo` is very efficient at returning large batches of data at once, so multi-threading will not provide any benefit in this case.

As a result, we approach the concurrency problem using a multi-processing workflow.

### Workflow

The figure below highlights the workflow used in the quote extractor and entity gender annotator's NLP functions.

![](img/concurrent.png)

We first run a one-time query to retrieve a large batch of ObjectIDs from MongoDB (either from a user-specified time period, or the entire dataset) - because the ObjectIDs are by default indexed by MongoDB, this is a relatively inexpensive query for even very large databases. We persist the cursor of IDs into a Python list (again, not expensive because we store just the IDs and no other information), following which we divide the list of IDs into batches, or *chunks* as shown in the image. 

Each available core on the machine takes in a single batch (20-50 article IDs at a time), retrieves the full article data for every item in the batch concurrently, and processes it for the NLP tasks (quote extraction and entity gender annotation). Once a batch is exhausted, it retrieves the next batch and repeats the same process, until all the batches from the entire list are exhausted. This process is very memory-efficient, and utilizes all available CPUs in the machine to the maximum possible extent. In case the script is run on a machine that is also responsible for hosting the database, the number of processes can be reduced using the `--poolsize` argument to ensure that some of the cores are always free for other essential tasks.

---

## Run quote extractor

### Default mode
By default, the quote extractor only works on articles that weren't processed earlier (i.e., new articles that are freshly scraped with `lastModifier = mediaCollectors`).

```sh
python3 quote_extractor.py --db mediaTracker --readcol media --limit 0
```
`--limit 0` (which is the default setting) means no limitation, and the script runs on all documents in the database. 

### Force update
To force-update the results and overwrite existing data for all articles, use the `--force_update` argument.
```sh
python3 quote_extractor.py --db mediaTracker --readcol media --force_update  --limit 10
```
`--limit 10` means that the script will process just 10 documents, which is useful during testing.

### Specify time period
We can easily limit the quote extraction process to only articles from a specified time period.

```sh
python3 quote_extractor.py --db mediaTracker --readcol media --force_update --begin_date 2020-01-01 --end_date 2020-01-31
```

For the full list of optional arguments, type the following:

```sh
python3 quote_extractor.py --help
```

## Run gender recognition service
This script starts a Flask server that provides routes for other modules to access the gender recognition service. All parameters for the gender API services are in the file `config.py`. Run this script with the default parameters:

```sh
python3 gender_recognition.py
```

## Run entity gender annotation

### Default mode
Just like the quote extractor, the entity gender annotator by default only works on articles that weren't processed earlier (i.e.,articles that were just processed by quote extractor, with `lastModifier = quote_extractor`).

```sh
python3 entity_gender_annotator.py --db mediaTracker --readcol media
```
Note that the gender recognition Flask server (from the previous step) must be started and running in production *before* the entity-gender annotator script can be run.

### Force update

To force-update the results and overwrite existing data for all articles, use the `--force_update` argument.

```sh
python3 entity_gender_annotator.py --db mediaTracker --readcol media --force_update
```

### Specify time period
We can easily limit the quote extraction process to only articles from a specified time period.

```sh
python3 entity_gender_annotator.py --db mediaTracker --readcol media --force_update --begin_date 2020-01-01 --end_date 2020-01-31
```

For further help options, type the following:

```sh
python3 entity_gender_annotator.py --help
```

---

## Processing data backlog for updates

When deploying upgrades to the NLP modules, it may be necessary to rerun the quote extractor and entity gender annotator on the **entire** database once again. To process such a large backlog containing several months' worth of data (hundreds of thousands of articles), a redundancy-based approach is recommended - rather than overwriting the existing data straightway, we output the entity gender annotation results to new collections, inspect them and then overwrite the old results with the new results using a merge script. The below steps were used for the V5.0 update. 

### 1. Run quote extractor as normal
The quote extraction step is a light-weight step, so an updated version of the quote extractor script can be run as shown above, which will overwrite the existing quotes in the existing collection ('media').

**Important**: It is strongly recommended to run the quote extractor update for several months of data in smaller batches, over one or two months at a time. This provides a failsafe in case the script stops running in the middle of an update for some reason. The best way to run it in batches is through a shell script, for example as shown below.

```sh
#!/usr/bin/sh
python3 quote_extractor.py --force_update --begin_date 2018-11-01 --end_date 2018-11-30
python3 quote_extractor.py --force_update --begin_date 2018-12-01 --end_date 2018-12-31
python3 quote_extractor.py --force_update --begin_date 2019-01-01 --end_date 2019-01-31
python3 quote_extractor.py --force_update --begin_date 2019-02-01 --end_date 2019-02-28

```

This shell script can then be run using nohup:

```sh
nohup bash run_quote_extractor.sh > quote_log.txt
```

### 2. Run entity gender annotator and write to new collection
Note that in the entity gender annotation step, specifying a `--writecol` argument **allows the results to be written to a new collection**. This is a very useful way to avoid overwriting existing data when testing new updates without affecting anything in production. An example is shown below.

```sh
python3 entity_gender_annotator.py --db mediaTracker --readcol media --writecol entitiesUpdated --force_update
```
This writes the entity gender annotation results to a new collection called 'entitiesUpdated'. These results can then be merged with the existing 'media' collection after carefully evaluating the results and ensuring that they didn't degrade in quality from the previous version.

**Important**: It is strongly recommended to run the entity gender annotator update in smaller batches, over one or two months of data at a time. This provides a failsafe in case the script stops running in the middle of an update for some reason. The best way to run it in batches is through a shell script, for example as shown below.

```sh
#!/usr/bin/sh
python3 entity_gender_annotator.py --force_update --writecol entities-2018-11-2018-12 --begin_date 2018-11-01 --end_date 2018-12-31
python3 entity_gender_annotator.py --force_update --writecol entities-2019-01-2019-02 --begin_date 2019-01-01 --end_date 2019-02-28
python3 entity_gender_annotator.py --force_update --writecol entities-2019-03-2019-04 --begin_date 2019-03-01 --end_date 2019-04-30
```
Again, specifying the `--writecol` argument as shown ensures that the results are written to a new collection each time - this method is strongly recommended to perform database updates in a non-intrusive manner.

This shell script can then be run using nohup:

```sh
nohup bash run_entity_gender_annotator.sh > entity_log.txt
```

### 3. Run merge script to overwrite existing fields with new results
Once a proper inspection of the new results is complete, they can be merged with the corresponding fields in the original `media` collection. This is done using the `merge_collections.py` script, which runs on all available cores to write the fields concurrently. 

```sh
python3 merge_collections.py --db mediaTracker --oldcol media --newcol entities-2018-10
```
The example command shown overwrites all entity gender annotator fields in the `media` collection with the values from the new collection `entities-2018-10` from the month October 2018.

Following this step, the entire database is updated and the aggregator script that processes daily data can then be run to update results on the live dashboard.

### 4. Rerun daily aggregator for Informed Opinions dashboard
The daily aggregator is a script (`GenderGapTracker/scraping_and_aggregation/tools.py`) that automatically runs once a day, aggregating the number of female/male sources for display on the [public dashboard](https://gendergaptracker.informedopinions.org/). To see the latest numbers from the previous step, this script can be manually run as follows.

```sh
cd GenderGapTracker/scraping_and_aggregation
python3 tools.py "generate_daily_collection"
```
The script takes about half an hour (as of September 2020) to run, following which the updated stats can be seen on the public dashboard.

### 5. Rerun monthly top sources scripts for research dashboard
Next, we need to update the precomputed stats for the research dashboard's top-quoted sources and monthly trends apps. The paths to the scripts that compute values for these apps are shown below:

* `GenderGapTracker/scraping_and_aggregation/monthly_aggregate/monthly_top_sources.py`
* `GenderGapTracker/scraping_and_aggregation/monthly_aggregate/monthly_top_sources_timeseries.py`

Script #1 calculates the top 15 sources for each month for either gender, used for displaying the top-quoted sources lollipop chart. Script #2 aggregates the total number of quotes for all sources (of either gender) that appeared in the top 50 sources for any given month.

#### Rerun script #1:
```sh
cd GenderGapTracker/scraping_and_aggregation/monthly_aggregate
python3 monthly_top_sources.py --begin_date 2020-08-01 --end_date 2020-08-31
```
Alternatively, a shell script is written that executes the script for each month separately. A snippet is shown below.

```sh
#!/usr/bin/sh
python3 monthly_top_sources.py --begin_date 2020-04-01 --end_date 2020-04-30
python3 monthly_top_sources.py --begin_date 2020-05-01 --end_date 2020-05-31
python3 monthly_top_sources.py --begin_date 2020-06-01 --end_date 2020-06-30
python3 monthly_top_sources.py --begin_date 2020-07-01 --end_date 2020-07-31
python3 monthly_top_sources.py --begin_date 2020-08-01 --end_date 2020-08-31
```

Execute the shell script using nohup: `nohup bash execute.sh > top_sources.out`

#### Rerun script #2 after deleting existing collection
To rerun script #2, i.e., the one that calculates the number of quotes per source as a time series, **simply rerunning the script is not enough**. During aggregation, if any preexisting sources disappeared in the current version (i.e., those that existed in the previous version but are now no longer valid sources), no automatic deletion of the old, out-of-date names/counts is performed (for safety reasons). As a result, **we must first delete the existing collection on the database before rerunning script #2**. This ensures that we do not serve any old results that are no longer valid on the monthly trends dashboard app.

The existing collection in the `mediaTracker` database for this app is called `monthlySourcesTimeSeries`. **Delete this collection** every time a new database update is performed on the full backlog.

Just as before, the update script can be run using a shell script.

```sh
#!/usr/bin/sh
python3 monthly_top_sources_timeseries.py --begin_date 2020-04-01 --end_date 2020-04-30
python3 monthly_top_sources_timeseries.py --begin_date 2020-05-01 --end_date 2020-05-31
python3 monthly_top_sources_timeseries.py --begin_date 2020-06-01 --end_date 2020-06-30
python3 monthly_top_sources_timeseries.py --begin_date 2020-07-01 --end_date 2020-07-31
python3 monthly_top_sources_timeseries.py --begin_date 2020-08-01 --end_date 2020-08-31
```
Execute the shell script using nohup: `nohup bash execute.sh > monthly_trends.out`
