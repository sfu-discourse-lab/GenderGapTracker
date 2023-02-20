config = {
    'MONGO_ARGS': {
        'host': ['mongo0', 'mongo1', 'mongo2'],
        # 'host': 'localhost',
        'port': 27017,
        'username': 'username',
        'password': 'password',
        'authSource': 'admin',
        'readPreference': 'primaryPreferred'
    },
    'DB': {
        'READ_DB': 'topicModel',
        'READ_COL': 'topicResults',
        'SOURCES_DB': 'mediaTracker',
        'SOURCES_COL': 'monthlySources',
        'GENDER_DB': 'genderCache',
        'MANUAL_NAME_COL': 'manual',
        'FIRST_NAME_COL': 'firstNamesCleaned',
    }
}