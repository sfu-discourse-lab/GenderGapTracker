# gunicorn_conf.py to point gunicorn to the uvicorn workers
from multiprocessing import cpu_count

# Socket path
bind = 'unix:/g-tracker/WomenInMedia/api/french/g-tracker-fr.sock'

# Worker Options
workers = cpu_count() - 1
worker_class = 'uvicorn.workers.UvicornWorker'

# Logging Options
loglevel = 'debug'
accesslog = '/g-tracker/WomenInMedia/api/french/access_log'
errorlog = '/g-tracker/WomenInMedia/api/french/error_log'
