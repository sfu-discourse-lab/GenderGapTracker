import datetime
import dash
from dash import dcc, html
from dash.dependencies import Input, Output, State
from pymongo import MongoClient
from server import app
from config import config

MONGO_ARGS = config['MONGO_ARGS']
SOURCES_DB = config['DB']['SOURCES_DB']
SOURCES_COL = config['DB']['SOURCES_COL']


# ========== Functions ================
def get_doc_ids_from_db():
    with MongoClient(**MONGO_ARGS) as connection:
        read_collection = connection[SOURCES_DB][SOURCES_COL]
        _ids = read_collection.find().distinct('_id')
    return sorted(_ids)


def num2str_month(date_str):
    date_obj = datetime.datetime.strptime(date_str, "%Y%m")
    date_string = datetime.datetime.strftime(date_obj, "%B %Y")
    return date_string


def format_dates(_ids):
    date_strings = [num2str_month(_id) for _id in _ids]
    return date_strings


def get_top_n_words(topic_dict, n=5):
    """Return a list of top-n words for each topic. This list can
       then be used as an axis label if required.
    """
    top_words = []
    for num, data in topic_dict.items():
        sorted_words = {k: v for k, v in sorted(data['words'].items(),
                                                key=lambda x: x[1],
                                                reverse=True
                                                )}
        words = sorted_words.keys()
        top_n_words = list(words)[:n]
        top_words.append(', '.join(top_n_words))
    return top_words


def list_topic_words(topic_dict):
    """Return a full list of words for a particular topic"""
    sorted_words = {k: v for k, v in sorted(topic_dict['words'].items(),
                                            key=lambda x: x[1],
                                            reverse=True
                                            )}
    words = sorted_words.keys()
    top_n_words = list(words)
    top_words = ', '.join(top_n_words)
    return top_words


# ========== App Layout ================

def layout():
    """Dynamically serve a layout based on updated DB values (for dropdown menu)"""
    # Needs db connection! (Set up tunnel if testing app locally)
    _ids = get_doc_ids_from_db()
    dropdown_dates = {num2str_month(_id): _id for _id in _ids}

    children_list = [
        html.Div([
            html.Div([
                html.H3('Write observations for monthly top sources by gender'),
                dcc.Markdown('''
                    This app allows a user to write observations and comments for a particular month's top quoted
                    sources. The text that is written is then saved on the database, and displayed on the [top sources
                    dashboard app](https://gendergaptracker.research.sfu.ca/apps/topsources).
                '''),
            ]),
            html.H4('Topic month'),
            html.P('''
                Select the topic month from the dropdown to inspect/update the word distributions for 
                that month.
            '''),
            html.Div(
                dcc.Loading(
                    id='load-data-progress',
                    children=[
                        dcc.Store(id='top-sources-stats'),
                    ])
            ),
            dcc.Dropdown(
                id='date-dropdown',
                options=[
                    {'label': date_str, 'value': date_num}
                    for date_str, date_num in dropdown_dates.items()
                ],
                value=_ids[-1],
                style={'text-align': 'center'}
            ),
            html.Br(),
            html.Label([
                html.A('Markdown syntax', href='https://www.markdownguide.org/basic-syntax/'),
            ]),
            html.P('''
                The text box below accepts Markdown syntax for embedding URLs: [Highlighted text](https://example.com).
                Make sure to route external URLs with the 'http' or 'https' prefix as shown in the
                example.
            '''),
        
            html.Div(id='create-text-input'),
            html.Div([html.Button(id='write-button', n_clicks=0, children='Save entries')],
                     style={'display': 'flex', 'justifyContent': 'center'}),
            dcc.Loading(
                id='write-progress',
                children=[
                    html.P(id='push-comment-fields')
                ], type='default'
            )
        ])
    ]
    return children_list


# ========== Callbacks ================
@app.callback(Output('top-sources-stats', 'data'), [Input('date-dropdown', 'value')])
def get_monthly_stats(value):
    with MongoClient(**MONGO_ARGS) as connection:
        read_collection = connection[SOURCES_DB][SOURCES_COL]
        stats = read_collection.find({'_id': value})
        # Collect top sources stats
        stats = list(stats)[0]
    return stats


@app.callback(Output('create-text-input', 'children'), [Input('top-sources-stats', 'data')])
def create_text_input(stats):
    comment = stats['comment']
    # Return the text area with existing comment (if any)
    inp_box = html.Div(
        dcc.Textarea(
            id='text-input',
            placeholder="Enter your comments/observations for the selected month's top sources",
            value=comment,
            className='textarea',
            style={
                'width': '100%', 'height': 350, 'verticalAlign': 'top',
                'fontFamily': 'Arial', 'fontColor': '#515151',
            }
        ),
        style={'display': 'flex', 'justifyContent': 'center'}
    ),
    return inp_box


@app.callback(Output('push-comment-fields', 'data'),
              [Input('write-button', 'n_clicks'),
               Input('date-dropdown', 'value'),
               Input('top-sources-stats', 'data')],
              [State('text-input', 'value')])
def update_db(n_clicks, date_id, stats, comment):
    """Check if write-button is clicked, only then update DB"""
    ctx = dash.callback_context
    if "write-button" in ctx.triggered[0]["prop_id"]:
        with MongoClient(**MONGO_ARGS) as connection:
            collection = connection[SOURCES_DB][SOURCES_COL]
            # Overwrite existing topic names with new user-entered names
            stats['comment'] = comment
            # Write topics
            collection.find_one_and_update({'_id': date_id}, {'$set': stats})
            return "Updated user comments/observations in the database.."
