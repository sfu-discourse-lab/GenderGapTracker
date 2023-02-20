host = ["mongo0", "mongo1", "mongo2"]
# host = "localhost"
is_direct_connection = True if (host == "localhost") else False

config = {
    "MONGO_HOST": host,
    "MONGO_PORT": 27017,
    "MONGO_ARGS": {
        "authSource": "admin",
        "readPreference": "primaryPreferred",
        "username": "username",
        "password": "password",
        "directConnection": is_direct_connection, 
    },
    "DB_NAME": "mediaTracker",
    "LOGS_DIR": "logs/",
}

