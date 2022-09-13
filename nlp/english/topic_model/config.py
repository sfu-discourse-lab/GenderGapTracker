config = {
    'MONGO_ARGS': {
        'host': ['mongo0', 'mongo1', 'mongo2'],
        'port': 27017,
        'username': 'username',
        'password': 'password',
        'authSource': 'admin',
        'readPreference': 'primaryPreferred'
    },
    'DB': {
        'READ_DB': 'mediaTracker',
        'READ_COL': 'media',
        'WRITE_DB': 'topicModel',
        'WRITE_COL': 'topicResults'
    },
    'MODEL': {
        'OUTLETS': [
            'National Post', 'The Globe And Mail', 'The Star',
            'Global News', 'CTV News', 'CBC News'
        ],
        'STOPWORDS': 'stopwords/stopwords.txt',
        'LEMMAS': 'spacyLemmas/spacy_english_lemmas.txt'
    }
}
