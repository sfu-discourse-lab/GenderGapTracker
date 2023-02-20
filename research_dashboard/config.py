host = ["mongo0", "mongo1", "mongo2"]
# host = "localhost"

config = {
    "MONGO_ARGS": {
        "host": host,
        "port": 27017,
        "username": "username",
        "password": "password",
        "authSource": "admin",
        "readPreference": "primaryPreferred",
    },
    "DB": {
        "READ_DB": "topicModel",
        "READ_COL": "topicResults",
        "SOURCES_DB": "mediaTracker",
        "SOURCES_COL": "monthlySources",
        "SOURCES_TIME_SERIES_COL": "monthlySourcesTimeSeries",
    },
    "GENDER_RECOGNITION": {
        "GENDERIZE_ENABLED": False,
        "GENDERAPI_ENABLED": True,
        "GENDERAPI_TOKEN": "JSON_AUTH_TOKEN",
        "MANUAL_CACHE": "manual",
        "GENDERAPI_CACHE": "genderAPICleaned",
        "GENDERIZE_CACHE": "genderizeCleaned",
        "FIRSTNAME_CACHE": "firstNamesCleaned",
    },
    "NLP": {
        "MAX_BODY_LENGTH": 20000,
        "AUTHOR_BLOCKLIST": "../nlp/english/rules/author_blocklist.txt",
        "NAME_PATTERNS": "../nlp/english/rules/name_patterns.jsonl",
        "QUOTE_VERBS": "../nlp/english/rules/quote_verb_list.txt",
    },
    "ENGLISH_OUTLETS": [
        "CBC News",
        "CTV News",
        "Global News",
        "Huffington Post",
        "National Post",
        "The Globe And Mail",
        "The Star",
    ],
    "FRENCH_OUTLETS": [
        "Journal De Montreal",
        "La Presse",
        "Le Devoir",
        "Le Droit",
        "Radio Canada",
        "TVA News",
    ],
}
