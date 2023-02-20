import flask
import os
import sys
import dash
# Logging
import logging
from logging.handlers import RotatingFileHandler
# auth.py simply contains a dictionary {'username': 'password'} that is used
# for basic HTTP authentication 
import dash_auth
from auth import credentials

server = flask.Flask(__name__)
server.secret_key = os.urandom(24)

app = dash.Dash(__name__, server=server, suppress_callback_exceptions=True)
app.css.config.serve_locally = True
app.scripts.config.serve_locally = True
app.title = "Write data to research dashboard - GGT"
# authentication
authorize = dash_auth.BasicAuth(app, credentials)


def create_app_logger(filename):
    """Logger format and timed handling"""
    logger = logging.getLogger(filename)
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    os.makedirs("logs", exist_ok=True)
    rotateHandler = RotatingFileHandler('logs/' + "g-tracker-admin-api.log",
                                        mode='a', maxBytes=1000, backupCount=3)
    rotateHandler.setFormatter(formatter)
    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(formatter)

    logger.addHandler(rotateHandler)
    logger.addHandler(stream)
    return logger


logger = create_app_logger('adminDashLogger')