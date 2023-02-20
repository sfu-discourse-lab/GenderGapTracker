import datetime
import pandas as pd
from dash import dcc, html, dash_table
from dash.dependencies import Input, Output
from pymongo import MongoClient
from server import app, logger
from config import config

MONGO_ARGS = config['MONGO_ARGS']
SOURCES_DB = config['DB']['SOURCES_DB']
SOURCES_COL = config['DB']['SOURCES_COL']
NUM_SOURCES_TO_SHOW = 20


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


def get_unknown_sources(stats):
    """Convert JSON object of top sources to pandas DataFrame"""
    top_unknown = pd.DataFrame(stats['topUnknownSources'])
    top_unknown.columns = ['unknown_count', 'unknown_names']
    top_unknown['unknown_count'] = top_unknown['unknown_count'].astype('int')
    df = (top_unknown.sort_values(by='unknown_count', ascending=False)
          .iloc[:NUM_SOURCES_TO_SHOW, :]
          .reset_index(drop=True))
    output = df.to_dict(orient='records')
    return output


# ========== App Layout ================

def layout():
    """Dynamically serve a layout based on updated DB values (for dropdown menu)"""
    # Needs db connection! (Set up tunnel if testing app locally)
    _ids = get_doc_ids_from_db()
    dropdown_dates = {num2str_month(_id): _id for _id in _ids}

    children_list = [
        html.Div([
            html.Div([
                html.H3('View unknown sources'),
                dcc.Markdown('''
                    This app allows a user to inspect the top unknown sources extracted for a 
                    particular month. The reason we obtain unknown sources is twofold—sometimes,
                    spaCy incorrectly tags an organization or geopolitical entity (i.e., location) as
                    a person, leading to the gender service erring on the side of caution and not 
                    assigning a gender. In other cases, a person's name is ambiguous, or is non-standard
                    (i.e., non-western or non-anglicized), so the gender services we use are unaware of 
                    these names' genders.

                    Inspect the list of unknown sources for a given month by choosing a 
                    month from the dropdown menu.
                '''),
            ]),
            dcc.Dropdown(
                id='date-dropdown',
                options=[
                    {'label': date_str, 'value': date_num}
                    for date_str, date_num in dropdown_dates.items()
                ],
                value=_ids[-1],
                style={'text-align': 'center'}
            ),
            html.Div(dcc.Store(id='top-sources-stats-2')),
            html.Br(),
            html.Div(
                dash_table.DataTable(
                    id='unknown-sources-table',
                    columns=[
                        {'name': 'Count', 'id': 'unknown_count'},
                        {'name': 'Unknown sources', 'id': 'unknown_names'},
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
                            'if': {'column_id': 'unknown_count'},
                            'minWidth': '100px',
                            'width': '100px',
                            'maxWidth': '100px',
                        },
                    ],
                    style_header={
                        'backgroundColor': 'rgb(255, 255, 255)',
                        'text-align': 'left',
                    },
                    style_as_list_view=True,
                )
            ),
            dcc.Markdown('''
                    #### 1. Fix spaCy NER rules
                    To address incorrect spaCy tags, we add a rule to the below file:   
                    [`WomenInMedia/NLP/main/rules/name_patterns.jsonl`](https://github.com/maitetaboada/WomenInMedia/blob/master/NLP/main/rules/name_patterns.jsonl)

                    The below tags are defined for now (others can be added as required):
                    * `GPE`: Countries, cities, states, famous landmarks
                    * `ORG`: Companies, agencies, institutions, etc.
                    * `FAC`: Buildings, airports, highways, bridges, etc.
                    * `NORP`: Nationalities or religious or political groups.
                    * `EVENT`: Named hurricanes, battles, wars, sports events, etc.

                    For a full list of tags, see the [spaCy documentation](https://spacy.io/api/annotation#named-entities).

                    #### 2. Update manual gender cache
                    Alteratively, for names that are of person (but are ambiguous), we can update the
                    manual gender cache (`genderCache/manual`). This is done by populating a CSV file 
                    with the correct gender for each person's name and running the manual cache update script:
                    [`WomenInMedia/NLP/experiments/genderCache/manual_cache`](https://github.com/maitetaboada/WomenInMedia/tree/master/NLP/experiments/genderCache/manual_cache)
            ''')
        ])
    ]
    return children_list


# ========== Callbacks ================

@app.callback(Output('top-sources-stats-2', 'data'), [Input('date-dropdown', 'value')])
def get_monthly_stats(value):
    with MongoClient(**MONGO_ARGS) as connection:
        read_collection = connection[SOURCES_DB][SOURCES_COL]
        stats = read_collection.find({'_id': value})
        # Collect top sources stats
        stats = list(stats)[0]
    return stats


@app.callback(Output('unknown-sources-table', 'data'), [Input('top-sources-stats-2', 'data')])
def get_unknown_sources_data(stats):
    try:
        output = get_unknown_sources(stats)
        logger.info(f'Obtained unknown sources of length {len(output)}')
    except Exception as e:
        logger.error("Unknown sources app error:", e)
        output = []
    return output


