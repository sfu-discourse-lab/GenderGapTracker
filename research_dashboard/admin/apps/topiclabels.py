import datetime
import dash
from dash import dcc, html, dash_table
from dash.dependencies import Input, Output, State

import pandas as pd
from pymongo import MongoClient
from server import app
from config import config

MONGO_ARGS = config['MONGO_ARGS']
DB = config['DB']['READ_DB']
COL = config['DB']['READ_COL']


# ========== Functions ================
def get_doc_ids_from_db():
    with MongoClient(**MONGO_ARGS) as connection:
        read_collection = connection[DB][COL]
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
                html.H3('Write topic labels to database'),
                dcc.Markdown('''
                    This app allows a user to inspect the results for monthly topics from our production
                    database, and update its topic labels so that they are human readable. The labels are 
                    directly written to the production database (without modifying any of the topic words themselves).

                    The write operation is quite safe - the only fields being overwritten are the topic "names",
                    i.e. the labels that represent what the topic stands for. This does not affect anything in production.
                    Once the write operation completes, head straight to the 
                    [topic model dashboard](https://gendergaptracker.research.sfu.ca/apps/topicmodel)
                    to inspect the updated the charts showing the topic breakdown.
                '''),
            ]),
            html.H4('Topic month'),
            html.P('''
                Select the topic month from the dropdown to inspect/update the word distributions for 
                that month.
            '''),
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
            html.Div(
                dcc.Loading(
                    id='loading-progress-1',
                    children=[
                        dcc.Store(id='topic-data-write')
                    ])
            ),
            html.Div(
                dash_table.DataTable(
                    id='topic-table-write',
                    columns=[
                        {'name': 'Topic', 'id': 'num'},
                        {'name': 'Topic labels', 'id': 'topic_names'},
                        {'name': 'Words', 'id': 'topic_words'}
                    ],
                    style_table={'overflowX': 'auto'},
                    style_cell={
                        'backgroundColor': 'rgba(102, 204, 204, 0.05)',
                        'textAlign': 'left',
                        'font_family': 'Arial',
                    },
                    style_data={'height': 'auto', 'lineHeight': '30px'},
                    style_cell_conditional=[
                        {
                            'if': {'column_id': 'num'},
                            'minWidth': '60px',
                            'width': '60px',
                            'maxWidth': '60px',
                        },
                    ],
                    style_header={
                        'backgroundColor': 'rgb(255, 255, 255)',
                        'text-align': 'left',
                    },
                    style_as_list_view=True,
                )
            ),
            html.Br(),
            html.H4('Label topics manually'),
            html.P('''
                Use 3-4 words to describe each topic distribution. Once finished, click on the
                "Save entries" button below to write the updated topic names to the database.          
            '''),
            html.Div(id='create-text-boxes'),
            html.Div([html.Button(id='write-button', n_clicks=0, children='Save entries')],
                    style={'display': 'flex', 'justifyContent': 'center'}),
            dcc.Loading(
                id='loading-progress-2',
                children=[
                    html.P(id='topic-name-fields')
                ], type='default'
            )
        ])
    ]
    return children_list


# ========== Callbacks ================
@app.callback(Output('topic-data-write', 'data'), [Input('date-dropdown', 'value')])
def get_topic_data(value):
    with MongoClient(**MONGO_ARGS) as connection:
        read_collection = connection[DB][COL]
        data = read_collection.find({'_id': value})
        # Collect data
        data = list(data)[0]
    return data


@app.callback(Output('create-text-boxes', 'children'), [Input('topic-data-write', 'data')])
def generate_table(data):
    topic_dict = data['topics']

    table_contents = []
    for key, val in topic_dict.items():
        table_contents += [
            html.Tr([html.Td(html.Label(f"Topic {key}:"))]),
            html.Tr([html.Td(html.P(f"{list_topic_words(val)}"))]),
            html.Tr([html.Td(dcc.Input(id=f"topic-{key}-id", value=val['name'], size='60'))]),
            html.Hr()
        ]
    return html.Table(table_contents)


@app.callback(Output('topic-table-write', 'data'),
              [Input('topic-data-write', 'data')])
def get_topic_words(data):
    topic_words = get_top_n_words(data['topics'], n=15)
    topic_nums = [key for key, value in data['topics'].items()]
    topic_names = [topic['name'] for topic in data['topics'].values()]

    topic_dict = {}
    topic_dict['num'] = topic_nums
    topic_dict['topic_names'] = topic_names
    topic_dict['topic_words'] = topic_words
    topicDF = pd.DataFrame.from_dict(topic_dict)
    output = topicDF.to_dict(orient='records')
    return output


@app.callback(Output('topic-name-fields', 'data'),
              [Input('write-button', 'n_clicks'),
               Input('date-dropdown', 'value'),
               Input('topic-data-write', 'data')],
              [State('topic-1-id', 'value'), State('topic-2-id', 'value'),
               State('topic-3-id', 'value'), State('topic-4-id', 'value'),
               State('topic-5-id', 'value'), State('topic-6-id', 'value'),
               State('topic-7-id', 'value'), State('topic-8-id', 'value'),
               State('topic-9-id', 'value'), State('topic-10-id', 'value'),
               State('topic-11-id', 'value'), State('topic-12-id', 'value'),
               State('topic-13-id', 'value'), State('topic-14-id', 'value'),
               State('topic-15-id', 'value')])
def update_db(n_clicks, date_id, topic_data, *names):
    """Check if write-button is clicked, only then update DB"""
    ctx = dash.callback_context
    if "write-button" in ctx.triggered[0]["prop_id"]:
        # Get updated user-entered topic names
        topic_names = {str(i + 1): name for i, name in enumerate(names)}

        with MongoClient(**MONGO_ARGS) as connection:
            collection = connection[DB][COL]
            # Overwrite existing topic names with new user-entered names
            for topic_num in topic_data['topics']:
                topic_data['topics'][topic_num]['name'] = topic_names[topic_num]
            # Write topics
            collection.find_one_and_update({'_id': date_id}, {'$set': topic_data})
            return "Updated database.."