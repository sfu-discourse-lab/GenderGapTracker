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
        'MEDIA_DB': 'mediaTracker',
        'MEDIA_COL': 'media',
        'TOPIC_DB': 'topicModel',
        'TOPIC_COL': 'topicResults'
    },
}
