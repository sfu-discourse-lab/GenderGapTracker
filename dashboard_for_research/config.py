config = {
    'MONGO_ARGS': {
        'host': ['mongo0', 'mongo1', 'mongo2'],
        'port': 27017,
        'username': USERNAME,
        'password': PASSWORD,
        'authSource': 'admin',
        'readPreference': 'primaryPreferred'
    },
    'DB': {
        'READ_DB': 'topicModel',
        'READ_COL': 'topicResults',
        'SOURCES_DB': 'mediaTracker',
        'SOURCES_COL': 'monthlySources',
        'SOURCES_TIME_SERIES_COL': 'monthlySourcesTimeSeries',
    },
    'GENDER_RECOGNITION': {
        'GENDERIZE_ENABLED': False,
        'GENDERAPI_ENABLED': True,
        'GENDERAPI_TOKEN': PRIVATE_PASSPHRASE,
        'HOST': 'localhost',
        'PORT': 5000
    },
    'NLP': {
        'MAX_BODY_LENGTH': 20000,
        'AUTHOR_BLOCKLIST': '../NLP/main/rules/author_blocklist.txt',
        'NAME_PATTERNS': '../NLP/main/rules/name_patterns.jsonl',
        'QUOTE_VERBS': '../NLP/main/rules/quote_verb_list.txt'
    }
}