# Scraping
This section contains the code we used for scraping news article content from various Canadian outlets, as well as added utilities for performing aggregations on the database for the dashboard. Note that we store all our data on a MongoDB database, so the scraper code shown in this repo can be modified accordingly if using any other database downstream. The code in this directory was tested on Python 3.6, but should be valid for higher versions.

## Required installations for scraping and data storage
 * MongoDB: Installation instructions [here](https://docs.mongodb.com/manual/tutorial/install-mongodb-on-ubuntu/).
 * Install Python 3.6+ and follow the below instructions to prepare the Python environment. Make sure that `gcc`, `build-essential` and `python3-devel` (on Red Hat/CentOS), or `python3-dev` (on ubuntu) are installed on the system. Also, install `python3-venv` for managing virtual environments.
 * Newspaper3k: We use our own [custom fork of the newspaper library](https://github.com/aleaugustoplus/newspaper) to help in the process of collecting data from news websites
     * Install the customized newspaper library into a Python virtual environment using the command `pip install -r requirements.txt` on the requirements file provided in this directory, [which is obtained from the source repo](https://github.com/aleaugustoplus/newspaper/blob/master/requirements.txt).


## News Sources
We scrape news articles from the following Canadian news organizations' websites. The articles in our database date back to October 2018.

#### English
1. CBC News
2. CTV News
3. Global News
4. HuffPost Canada<sup>*</sup>
5. National Post
6. The Globe And Mail
7. The Star

> <sup>*</sup> HuffPost Canada stopped publishing articles in March 2021. As a result, our database only contains articles from this outlet until February 2021.

#### French
1. Journal De Montreal
2. La Presse
3. Le Devoir
4. Le Droit
5. Radio Canada
6. TVA News

Each outlet's news content is retrieved from their RSS feeds by running the required media collectors. Some examples of usage are shown below.

### Example of usage

Run the `mediaCollectors.py` script with positional arguments pointing to the (case-sensitive) news outlet name as follows.

```sh
python3 WomenInMedia/scraper/mediaCollectors.py "Huffington Post"
python3 WomenInMedia/scraper/mediaCollectors.py "Journal De Montreal"
```


### `config.py` parameters
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
EMAIL_SERVER = 'xxxx@smtp.gmail.com'
EMAIL = "youremail@gmail.com"
EMAIL_ACCOUNT = ""
EMAIL_PASSWORD = ""
EMAIL_DESTINATION = ""
```
