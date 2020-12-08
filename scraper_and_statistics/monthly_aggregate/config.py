config = {
    'MONGO_ARGS': {
        'host': ['mongo0', 'mongo1', 'mongo2'],
        'port': 27017,
        'username': USERNAME,
        'password': PASSWORD,
        'authSource': 'admin',
        'readPreference': 'nearest',
    }
}