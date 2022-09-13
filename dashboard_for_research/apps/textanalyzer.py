import json
import urllib
from urllib.request import urlopen
# Dash
from plotly.subplots import make_subplots
import plotly.graph_objects as go
import dash
import dash_core_components as dcc
import dash_html_components as html
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output, State
from dash_table import DataTable
from server import app, spacy_lang, logger
# NLP modules
import sys
import os
import requests

sys.path.append(os.path.abspath('../nlp/english'))
import utils
from config import config
from quote_extractor import QuoteExtractor
from entity_gender_annotator import EntityGenderAnnotator

GENDER_RECOGNITION_SERVICE = 'http://{}:{}'.format('localhost', 5000)
config["spacy_lang"] = spacy_lang
config["session"] = requests.Session()
config["NLP"]["QUOTE_VERBS"] = os.path.abspath('../nlp/english/rules/quote_verb_list.txt')
config["NLP"]["AUTHOR_BLOCKLIST"] = os.path.abspath('../nlp/english/rules/author_blocklist.txt')
extractor = QuoteExtractor(config)
annotator = EntityGenderAnnotator(config)

# ========== App Layout ================

def layout():
    children_list = [
        html.Div(
            children=[
                html.Div([
                    html.H2('Analyzing gender balance'),
                    html.P('''
                        Analyze your article's text for gender balance in the sources quoted and people mentioned.
                        Click on the "submit" button to see the people quoted and mentioned in
                        your text, broken down by gender.
                    ''')],
                ),
                html.Div(
                    dcc.Textarea(
                        id='text-input',
                        placeholder='Enter your text to be analyzed',
                        className='textarea',
                        style={
                            'width': '100%', 'height': 250, 'verticalAlign': 'top',
                            'fontFamily': 'Arial', 'fontColor': '#515151',
                        }
                    ),
                    style={'display': 'flex', 'justifyContent': 'center'}
                ),
                html.Div(
                    [html.Button(id='submit', n_clicks=0, children='Submit'),
                     html.Button(id='reset', n_clicks=0, children='Reset', style={'backgroundColor': 'white'})],
                     style={'display': 'flex', 'justifyContent': 'center'}),
                html.Br(),
                dbc.Alert(
                    "Text sample is too long! Please submit smaller chunks, each less than 20,000 characters in length.",
                    color="danger",
                    id="alert-auto",
                    is_open=False,
                    dismissable=True,
                ),
                html.Div([
                    dcc.Loading(
                        id='loading-progress-1',
                        children=[
                            html.Div([
                                dcc.Store(id='sources-and-people-data'),
                                dcc.Store(id='quote-data'),
                            ]),
                        ], type="circle")
                    ]),
                html.Br(),
                html.Div([
                    dcc.Loading(
                        id='loading-progress-2',
                        children=[
                            html.Div([dcc.Graph(id='pie-charts')], className='chart'),
                            html.Hr(),
                            html.H4('Breakdown: sources quoted'), 
                            html.Div(id='sources-table'),
                            html.H4('Breakdown: people mentioned'),
                            html.Div(id='people-table'),
                            html.Hr(),
                            html.H4('Speakers and quotes detected'),
                            html.Div(id='quote-table'),
                        ], type="circle"
                    )
                ]),
            ]
        ),
    ]
    return children_list


# ========== Callbacks ================

@app.callback([Output('sources-and-people-data', 'data'),
               Output('quote-data', 'data'),
               Output("alert-auto", "is_open")],
              [Input('submit', 'n_clicks'),
               Input('reset', 'n_clicks')],
              [State('text-input', 'value')])
def update_people_data(submit_button, reset_button, input_text):
    """Return the male, female and unknown sources from the NLP function call"""
    ctx = dash.callback_context
    empty_people = {'female': [], 'male': [], 'unknown': []}  # empty value for people and sources
    empty_quotes = [{'quote': '', 'speaker': ''}]   # empty value for quotes and speakers
    # Empty input text or reset button click returns nothing
    if not input_text or "reset" in ctx.triggered[0]["prop_id"]:
        return {'sources': empty_people, 'people': empty_people}, empty_quotes, False
    else:
        flag = False
        if len(input_text) > 20_000:
            # If the input text is too long, provide an error message to the user.
            sources_and_people = {'sources': empty_people, 'people': empty_people}
            quotes_and_sources = empty_quotes
            flag = True
        else:
            # Extract quotes and person named entities from input text
            people, sources, quotes_and_sources = extract_quotes_and_entities(input_text)
            # Extract people mentioned and quoted sources from the named entities
            sources_and_people = get_sources_and_people(people, sources)
        return sources_and_people, quotes_and_sources, flag


@app.callback(Output('text-input', 'value'), [Input('reset', 'n_clicks')])
def clear_form(n_clicks):
    """Empty input textarea"""
    return ""


@app.callback(Output("pie-charts", "figure"), [Input('sources-and-people-data', 'data')])
def update_source_gender_pie(data):
    """Update pie chart subplots with source/people count breakdown per gender"""
    return get_pie_subplots(data)


@app.callback(Output("sources-table", "children"),
              [Input('sources-and-people-data', 'data'),
              Input('submit', 'n_clicks')])
def update_source_table(data, n_clicks):
    # Generate formatted data for datatable
    if n_clicks > 0 and data is not None:
        display_data = people_by_gender(data['sources'], 'sources')
        return DataTable(
            id="source-table-id",
            data=display_data,
            columns=[
                {'name': 'Gender', 'id': 'gender'},
                {'name': '#', 'id': '#'},
                {'name': 'Names', 'id': 'names'}
            ],
            style_table={'overflowX': 'auto'},
            style_cell={
                'backgroundColor': 'rgba(102, 204, 204, 0.05)',
                'textAlign': 'left',
                'font_family': 'Arial',
                'padding': '0px 10px',
            },
            style_cell_conditional=[
                {
                    'if': {'column_id': 'gender'},
                    'width': '120px',
                    'min-width': '120px',
                    'max-width': '120px'
                },
                {
                    'if': {'column_id': '#'},
                    'width': '40px',
                    'min-width': '40px',
                    'max-width': '40px' 
                }
            ],
            style_data={'height': 'auto', 'lineHeight': '30px'},
            style_header={
                'backgroundColor': 'rgb(255, 255, 255)',
                'text-align': 'left',
            },
            style_as_list_view=True,
        )


@app.callback(Output("people-table", "children"),
              [Input('sources-and-people-data', 'data'),
              Input('submit', 'n_clicks')])
def update_people_table(data, n_clicks):
    if n_clicks > 0 and data is not None:
        display_data = people_by_gender(data['people'], 'people')
        return DataTable(
            id="people-table-id",
            data=display_data,
            columns=[
                {'name': 'Gender', 'id': 'gender'},
                {'name': '#', 'id': '#'},
                {'name': 'Names', 'id': 'names'}
            ],
            style_table={'overflowX': 'auto'},
            style_cell={
                'backgroundColor': 'rgba(102, 204, 204, 0.05)',
                'textAlign': 'left',
                'font_family': 'Arial',
                'padding': '0px 10px',
            },
            style_cell_conditional=[
                {
                    'if': {'column_id': 'gender'},
                    'width': '120px',
                    'min-width': '120px',
                    'max-width': '120px'
                },
                {
                    'if': {'column_id': '#'},
                    'width': '40px',
                    'min-width': '40px',
                    'max-width': '40px' 
                }
            ],
            style_data={'height': 'auto', 'lineHeight': '30px'},
            style_header={
                'backgroundColor': 'rgb(255, 255, 255)',
                'text-align': 'left',
            },
            style_as_list_view=True,
        )


@app.callback(Output("quote-table", "children"),
              [Input('quote-data', 'data'),
              Input('submit', 'n_clicks')])
def update_quote_table(quotes_and_sources, n_clicks):
    if n_clicks > 0:
        return DataTable(
            id="quote-table-id",
            data=quotes_and_sources,
            columns=[
                {'name': 'Speaker', 'id': 'speaker'},
                {'name': 'Quote', 'id': 'quote'},
            ],
            style_table={'overflowX': 'auto'},
            style_cell={
                'backgroundColor': 'rgba(102, 204, 204, 0.05)',
                'textAlign': 'left',
                'font_family': 'Arial',
                'padding': '0px 10px',
            },
            style_data={'height': 'auto', 'lineHeight': '30px'},
            style_header={
                'backgroundColor': 'rgb(255, 255, 255)',
                'text-align': 'left',
            },
            style_as_list_view=True,
        )


# ========== Functions ================

def get_genders(people):
    """Utilize gender recognition service to extract a name's gender"""
    some_url = '{}/get-genders?people={}'.format(GENDER_RECOGNITION_SERVICE,
                                                 urllib.parse.quote(','.join(people)))
    response = urlopen(some_url)
    data = json.load(response)
    return data


def format_names(name_list):
    """Format output string from extracted sources/mentions"""
    formatted = f"{(', ').join(name_list)}" if name_list else ""
    return formatted


def collect_quotes(quotes):
    """Structure final quotes as a list of records for display in a table."""
    collection = []
    for q in quotes:
        # Checking for 'PERSON' before assigning a speaker - if the quote is of type 'Heuristic',
        # the conditions are relaxed and we accept the quote with a blank speaker name
        if q.get('named_entity_type') == 'PERSON' or q.get('quote_type') == 'Heuristic':
            speaker = q.get('named_entity', "")
            quote = utils.preprocess_text(q.get('quote', ""))
            collection.append({'speaker': speaker, 'quote': quote})
    return collection


def people_by_gender(name_dict, category):
    """Return the person and source names for each gender as comma-separated strings"""
    female_names = format_names(name_dict['female'])
    male_names = format_names(name_dict['male'])
    unknown_names = format_names(name_dict['unknown'])
    names = [female_names, male_names, unknown_names]
    genders = ['woman', 'man', 'unknown']
    # Create a list of records to store in a table
    records = []
    for gender, name_list in zip(genders, names):
        name_ = name_list.split(',') if name_list else ""
        records.append({'gender': gender, '#': len(name_), 'names': name_list})
    return records


def extract_quotes_and_entities(sample_text):
    """Convert raw text to a spaCy doc object and return its named entities and quotes"""
    text = utils.preprocess_text(sample_text)
    doc = spacy_lang(text)
    quotes = extractor.extract_quotes(doc)
    annotation = annotator.run(text, [], quotes, "")
    people = annotation["people"]
    sources = annotation["sources"]
    unified_nes = annotator.merge_nes(doc)
    named_entities = annotator.remove_invalid_nes(unified_nes)
    # Get list of people and sources, along with a combined list of all quotes
    # Obtain gender of speakers from condensed coreference clusters
    _, _, all_quotes = annotator.quote_assign(named_entities, quotes, doc)
    quotes_and_sources = collect_quotes(all_quotes)
    # sort alphabetically based on speaker name
    quotes_and_sources = sorted(quotes_and_sources, key=lambda x: x['speaker'], reverse=True)
    # Get proper list of sources from the list of quotes and speakers
    sources = list(set([person['speaker'] for person in quotes_and_sources]))
    # Merge list of people and sources (in case there is a mismatch) to get full list of people
    people = list(set(people).union(set(sources)))
    return people, sources, quotes_and_sources


def get_sources_and_people(people, sources):
    """Collect sources and people mentioned in the text based on their gender."""
    people_genders = get_genders(people)
    sources_and_people = dict()
    temp = dict()
    for val in ['female', 'male', 'unknown']:
        temp[val] = [person for person, gender in people_genders.items()
                     if gender == val and person in sources]
        temp[val] = list(filter(bool, temp[val]))
    sources_and_people['sources'] = temp

    temp = dict()
    for val in ['female', 'male', 'unknown']:
        temp[val] = [person for person, gender in people_genders.items()
                     if gender == val]
        temp[val] = list(filter(bool, temp[val]))
    sources_and_people['people'] = temp
    logger.info(sources_and_people)

    return sources_and_people


def get_pie_counts(data, category='sources'):
    """Calculate number of sources/people per gender for pie chart"""
    people = data[category]
    female_count = len(people['female'])
    male_count = len(people['male'])
    unknown_count = len(people['unknown'])
    values = [female_count, male_count, unknown_count]
    text = [f"{count} {category} detected" for count in values]
    return values, text


def get_pie_subplots(data):
    """Create pie chart subplot figure objects for dash"""
    source_values, source_text = get_pie_counts(data, 'sources')
    people_values, people_text = get_pie_counts(data, 'people')
    empty_annotations = [dict(text='', showarrow=False), dict(text='', showarrow=False)]
    trace1 = go.Pie(
        values=source_values,
        labels=['Women', 'Men', 'Unknown'],
        name='Sources',
        marker=dict(
            dict(
                colors=['rgb(175, 24, 88)', 'rgb(0, 77, 114)', 'rgb(200, 200, 200)']),
                line=dict(color='rgb(250, 250, 250)', width=2,
            )
        ),
        hole=0.45,
        text=source_text,
        textinfo='percent',
        textposition='inside',
        hoverinfo='percent+label+text',
        sort=False     
    )

    trace2 = go.Pie(
        values=people_values,
        labels=['Women', 'Men', 'Unknown'],
        name='People',
        marker=dict(
            dict(
                colors=['rgb(175, 24, 88)', 'rgb(0, 77, 114)', 'rgb(200, 200, 200)']),
                line=dict(color='rgb(250, 250, 250)', width=2,
            )
        ),
        hole=0.45,
        text=people_text,
        textinfo='percent',
        textposition='inside',
        hoverinfo='percent+label+text',
        sort=False  
    )

    fig = make_subplots(rows=1, cols=2, specs=[[{"type": "domain"}, {"type": "domain"}]])
    fig.add_trace(trace1, row=1, col=1)
    fig.add_trace(trace2, row=1, col=2)
    fig['layout'].update(
        height=400,
        width=800,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        legend=dict(orientation='h', x=0.25, y=-0.1, font=dict(size=16)),
        margin=dict(l=20, r=80, t=50, b=50),
        annotations=[
            dict(text='Proportion of women/men quoted', x=0.05, y=1.15, showarrow=False, font=dict(size=16)),
            dict(text='Proportion of women/men mentioned', x=0.96, y=1.15, showarrow=False, font=dict(size=16)),
        ] if not data['people'] == {'female': [], 'male': [], 'unknown': []} else empty_annotations
    )
    return fig
