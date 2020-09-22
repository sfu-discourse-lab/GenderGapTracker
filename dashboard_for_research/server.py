import flask
import os
import dash
# For language model and loggers
import sys
import spacy
import neuralcoref
import logging
from logging.handlers import RotatingFileHandler

server = flask.Flask(__name__)
server.secret_key = os.urandom(24)

app = dash.Dash(__name__, server=server, suppress_callback_exceptions=True)
app.title = "Measuring gender bias in media - SFU"
app.css.config.serve_locally = True
app.scripts.config.serve_locally = True


def create_app_logger(filename):
    """Logger format and timed handling"""
    logger = logging.getLogger(filename)
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    rotateHandler = RotatingFileHandler('logs/' + "g-tracker-research-api.log",
                                        mode='a', maxBytes=1000, backupCount=3)
    rotateHandler.setFormatter(formatter)
    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(formatter)

    logger.addHandler(rotateHandler)
    logger.addHandler(stream)
    return logger


def load_spacy_lang(lang='en_core_web_sm'):
    """Return a specific spaCy language model for the NLP module"""
    logger.info(f"Loading spaCy language model: '{lang}'")
    nlp = spacy.load(lang)
    logger.info("Done...")
    # Add neuralcoref pipe
    coref = neuralcoref.NeuralCoref(nlp.vocab, max_dist=200)
    nlp.add_pipe(coref, name='neuralcoref')
    return nlp


logger = create_app_logger('userInputDashLogger')
# Load spaCy Model
spacy_lang = load_spacy_lang('en_core_web_sm')
# Specify gender recognition service IP and port
GENDER_RECOGNITION_SERVICE = 'http://{}:{}'.format('localhost', 5000)