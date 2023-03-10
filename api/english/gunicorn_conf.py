# gunicorn_conf.py to point gunicorn to the uvicorn workers
from multiprocessing import cpu_count

# Socket path
bind = 'unix:/g-tracker/WomenInMedia/api/english/g-tracker.sock'

# Worker Options
workers = cpu_count() - 1
worker_class = 'uvicorn.workers.UvicornWorker'

# Logging Options
loglevel = 'debug'
accesslog = '/g-tracker/WomenInMedia/api/english/access_log'
errorlog = '/g-tracker/WomenInMedia/api/english/error_log'
