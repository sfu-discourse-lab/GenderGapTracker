import flask
import os
import dash
import dash_bootstrap_components as dbc
# For language model and loggers
import sys
import spacy
import neuralcoref
from spacy.pipeline import EntityRuler
import logging
from logging.handlers import RotatingFileHandler

server = flask.Flask(__name__)
server.secret_key = os.urandom(24)

app = dash.Dash(
    __name__,
    server=server,
    suppress_callback_exceptions=True,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    meta_tags=[
        {
            'name': 'Measuring gender bias in media - SFU',
            'content': 'A dashboard to analyze gender discrepancies in mainstream Canadian news media.'
        },
        {
            'property': 'og:image',
            'content': 'https://www.sfu.ca/content/sfu/discourse-lab/jcr:content/main_content/image_0.img.2000.high.jpg/1499291765186.jpeg',
        }
    ],
)
app.title = "Measuring gender bias in media - SFU"
# Serve JS and CSS locally
app.css.config.serve_locally = True
app.scripts.config.serve_locally = True


def create_app_logger(filename):
    """Logger format and timed handling"""
    logger = logging.getLogger(filename)
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    os.makedirs("logs", exist_ok=True)
    rotateHandler = RotatingFileHandler('logs/' + "g-tracker-research-api.log",
                                        mode='a', maxBytes=1_000_000, backupCount=3)
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
print('Loading spaCy language model...')
spacy_lang = spacy.load('en_core_web_sm')
# Add custom named entity rules for non-standard person names that spaCy doesn't automatically identify
ruler = EntityRuler(spacy_lang, overwrite_ents=True).from_disk('../nlp/english/rules/name_patterns.jsonl')
spacy_lang.add_pipe(ruler)
# Add neuralcoref pipe
coref = neuralcoref.NeuralCoref(spacy_lang.vocab, max_dist=200)
spacy_lang.add_pipe(coref, name='neuralcoref')
print('Finished loading.')

