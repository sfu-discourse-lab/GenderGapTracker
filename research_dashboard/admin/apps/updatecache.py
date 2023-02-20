import dash
from dash import dcc, html
from dash.dependencies import Input, Output, State

from pymongo import MongoClient
from server import app
from config import config
# NLP modules
import sys
import os
sys.path.append(os.path.abspath('../../nlp/english'))
import utils

MONGO_ARGS = config['MONGO_ARGS']
GENDER_DB = config['DB']['GENDER_DB']
MANUAL_NAME_COL = config['DB']['MANUAL_NAME_COL']
FIRST_NAME_COL = config['DB']['FIRST_NAME_COL']


# ========== Functions ================
def upsert_cache(gender_cache_col, name, gender):
    """
    Insert or update a manually annotated gender entry in the database.
    We perform TWO inserts, for cases where we have names with accented characters.
      - The first insert is for the French pipeline (where we retain accents for gender prediction)
      - The second insert is for the English pipeline (where we DO NOT retain accents for gender prediction)
    """
    # Lowercase names before entry
    name = name.lower()
    # Insert #1 with accents, but lowercased
    gender_cache_col.update_one(
        {'name': name},
        {'$set': {'gender': gender}},
        upsert=True,
    )
    # Remove special characters from names (e.g., apostrophes)
    name = utils.clean_ne(name)
    # Clean name of unicode (accented characters)
    name = utils.remove_accents(name)
    # Insert #2 without accents
    gender_cache_col.update_one(
        {'name': name},
        {'$set': {'gender': gender}},
        upsert=True,
    )


# ========== App Layout ================

def layout():
    """Dynamically serve a layout"""
    children_list = [
        html.Div([
            html.Div([
                html.H3('Write a full name or first name to the gender cache'),
                dcc.Markdown('''
                    This app allows a user to update our manual (full name) or first name
                    gender cache. The typical use case for this app is when we see the same
                    person's name appear quite regularly in the "unknown" gender category.
                    To prevent this name from being repeatedly categorized as unknown gender,
                    it makes sense to update either the first name or the full name of the 
                    person in our gender cache. Following this, we can simply rerun the NLP
                    pipeline on the recent backlog to recompute the true gender counts.

                    Use the below rules of thumb to decide which cache to update:  
                      - For non-western names that are unambiguous in gender, e.g., *Mahmoudou*,
                      which is an unambiguously male name, we can be confident that nearly all
                      names that have this as a first name will be male, **regardless of the last
                      name**, so this name can go in the **first name cache**.  
                      - For names that have some ambiguity, e.g., *Lindsey Graham* (the South
                      Carolina senator), we don't want to make the assumption that the first name
                      "Lindsey" is always male, so in such cases, it makes sense to update the 
                      **manual cache** exact instances of the full name.
                '''),
            ]),
            html.H4('Full name with gender'),
            html.P('''
                Enter the full name (exactly as it appears in the news) along with its
                correct gender. This will be updated in the manual cache.
            '''),
            html.Div(
                html.Table([
                    html.Tr([
                        html.Td(dcc.Markdown('__Enter full name__')),
                        html.Td(dcc.Input(id='full-name-input', size='20')),
                    ]),
                    html.Tr([
                        html.Td(dcc.Markdown('__Select gender__')),
                        html.Td(
                            dcc.Dropdown(
                                id='full-name-gender-dropdown',
                                options=[
                                    {'label': 'male', 'value': 'male'}, 
                                    {'label': 'female', 'value': 'female'}, 
                                    {'label': 'unknown', 'value': 'unknown'}, 
                                ],
                                value='male',
                            )
                        )
                    ]),
                ])
            ),
            html.Div([html.Button(id='full-name-write-button', n_clicks=0, children='Update manual cache')],
                     style={'display': 'flex'}),
            dcc.Loading(
                id='loading-progress-1',
                children=[
                    html.P(id='full-name-result')
                ], type='default'
            ),
            html.Hr(),
            html.H4('First name with gender'),
            html.P('''
                Enter the first name (exactly as it appears in the news) along with its
                correct gender. This will be updated in the first name cache.
            '''),
            html.Div(
                html.Table([
                    html.Tr([
                        html.Td(dcc.Markdown('__Enter first name__')),
                        html.Td(dcc.Input(id='first-name-input', size='20')),
                    ]),
                    html.Tr([
                        html.Td(dcc.Markdown('__Select gender__')),
                        html.Td(
                            dcc.Dropdown(
                                id='first-name-gender-dropdown',
                                options=[
                                    {'label': 'male', 'value': 'male'}, 
                                    {'label': 'female', 'value': 'female'}, 
                                    {'label': 'unknown', 'value': 'unknown'}, 
                                ],
                                value='male',
                            )
                        )
                    ]),
                ])
            ),
            html.Div([html.Button(id='first-name-write-button', n_clicks=0, children='Update first name cache')],
                     style={'display': 'flex'}),
            dcc.Loading(
                id='loading-progress-2',
                children=[
                    html.P(id='first-name-result')
                ], type='default'
            ),
        ])
    ]
    return children_list


# ========== Callbacks ================
@app.callback(Output('full-name-result', 'data'),
              [Input('full-name-write-button', 'n_clicks'),
               Input('full-name-gender-dropdown', 'value')],
              [State('full-name-input', 'value')])
def update_manual_db(n_clicks, gender, name):
    """Take full name inputs from the user and write to manual cache"""
    ctx = dash.callback_context
    if "full-name-write-button" in ctx.triggered[0]["prop_id"]:
        with MongoClient(**MONGO_ARGS) as connection:
            collection = connection[GENDER_DB][MANUAL_NAME_COL]
            # Overwrite (i.e. upsert) existing name with new name-gender pair
            upsert_cache(collection, name, gender)
            return "Updated manual cache.."


@app.callback(Output('first-name-result', 'data'),
              [Input('first-name-write-button', 'n_clicks'),
               Input('first-name-gender-dropdown', 'value')],
              [State('first-name-input', 'value')])
def update_first_name_db(n_clicks, gender, name):
    """Take first name inputs from the user and write to first name cache"""
    ctx = dash.callback_context
    if "first-name-write-button" in ctx.triggered[0]["prop_id"]:
        with MongoClient(**MONGO_ARGS) as connection:
            collection = connection[GENDER_DB][FIRST_NAME_COL]
            # Overwrite (i.e. upsert) existing name with new name-gender pair
            upsert_cache(collection, name, gender)
            return "Updated first name cache.."

