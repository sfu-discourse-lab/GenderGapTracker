# gunicorn_conf.py to point gunicorn to the uvicorn workers
from multiprocessing import cpu_count

# Socket path
bind = 'unix:/path_to_code/GenderGapTracker/api/english/g-tracker.sock'

# Worker Options
workers = cpu_count() + 1
worker_class = 'uvicorn.workers.UvicornWorker'

# Logging Options
loglevel = 'debug'
accesslog = '/path_to_code/GenderGapTracker/api/english/access_log'
errorlog = '/path_to_code/GenderGapTracker/api/english/error_log'
