host = ["mongo0", "mongo1", "mongo2"]
# host = "localhost"
prefix = "." if (host == "localhost") else "/path_to_code/GenderGapTracker/nlp/french"

config = {
    "MONGO_ARGS": {
        "host": host,
        "port": 27017,
        "authSource": "admin",
        "readPreference": "primaryPreferred",
        "username": "username",
        "password": "password",
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
        "QUOTE_VERBS": f"{prefix}/rules/quote_verb_list.txt",
        "AUTHOR_BLOCKLIST": f"{prefix}/rules/author_blocklist.txt",
        "NAME_PATTERNS": f"{prefix}/rules/name_patterns.jsonl",
    },
}
