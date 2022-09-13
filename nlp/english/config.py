config = {
    'MONGO_ARGS': {
        'host': ['mongo0', 'mongo1', 'mongo2'],
        'port': 27017,
        'username': 'username',
        'password': 'password',
        'authSource': 'admin',
        'readPreference': 'nearest'
    },
    'GENDER_RECOGNITION': {
        'GENDERIZE_ENABLED': False,
        'GENDERAPI_ENABLED': True,
        'GENDERAPI_TOKEN': 'PRIVATE_PASSPHRASE',
        'HOST': 'localhost',
        'PORT': 5000
    },
    'NLP': {
        'MAX_BODY_LENGTH': 20000,
        'AUTHOR_BLOCKLIST': '/path_to_project/nlp/english/rules/author_blocklist.txt',
        'NAME_PATTERNS': '/path_to_project/nlp/english/rules/name_patterns.jsonl',
        'QUOTE_VERBS': '/path_to_project/nlp/english/rules/quote_verb_list.txt'
    }
}
