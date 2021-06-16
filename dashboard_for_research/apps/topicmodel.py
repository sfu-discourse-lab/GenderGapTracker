import datetime
import pandas as pd
from pymongo import MongoClient
# Dash
import dash_html_components as html
import dash_core_components as dcc
from dash.dependencies import Input, Output, State
from dash_table import DataTable
# Server and settings
from server import app
from config import config

MONGO_ARGS = config['MONGO_ARGS']
READ_DB = config['DB']['READ_DB']
READ_COL = config['DB']['READ_COL']


# ========== Functions ================
def get_doc_ids_from_db():
    with MongoClient(**MONGO_ARGS) as connection:
        read_collection = connection[READ_DB][READ_COL]
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


def construct_outletDF(data_dict):
    """Convert the topic distribution per outlet to a DataFrame and reorder by magnitude"""
    outlet_dict = data_dict['perOutletTopics']
    topics = data_dict['topics']
    # Convert to Pandas DataFrame
    outlet_topicsDF = pd.DataFrame.from_dict(outlet_dict, orient='index').sort_index().transpose()
    outlet_topicsDF['sum'] = outlet_topicsDF[outlet_topicsDF.columns].sum(axis=1)
    # Sort in descending order of the sum of mean values for each topic
    outlet_topicsDF = outlet_topicsDF.sort_values('sum').drop('sum', axis=1)

    # Get a properly ordered list of topics based on prominence for axis labelling
    ordered_topics_dict = {idx: topics[idx] for idx in outlet_topicsDF.index}
    ordered_names = [topics[idx]['name'] for idx in outlet_topicsDF.index]
    top_5_words = get_top_n_words(ordered_topics_dict)
    # Get topic names for axis labels if they exist, otherwise return top-5 words per topic
    y_labels = [name if name else top_5_words[i] for i, name in enumerate(ordered_names)]
    return outlet_topicsDF, y_labels


def construct_gender_df(data_dict):
    """Convert the topic distribution per gender to a DataFrame and reorder by magnitude"""
    gender_dict = data_dict['perGenderTopics']
    topics = data_dict['topics']
    # Convert to Pandas DataFrame
    genderDF = pd.DataFrame.from_dict(gender_dict, orient='index').transpose()
    genderDF = genderDF[['female', 'male']]
    genderDF['diff'] = genderDF['female'] - genderDF['male']
    # Sort in order of the sum of mean values for each topic
    genderDF = genderDF.sort_values('diff')
    genderDF['topic'] = [f"t{i}" for i in genderDF.index]

    # Get a properly ordered list of topics based on prominence for axis labelling
    ordered_topics_dict = {idx: topics[idx] for idx in genderDF.index}
    ordered_names = [topics[idx]['name'] for idx in genderDF.index]
    top_5_words = get_top_n_words(ordered_topics_dict)
    # Get topic names for axis labels if they exist, otherwise return top-5 words per topic
    y_labels = [name if name else top_5_words[i] for i, name in enumerate(ordered_names)]
    genderDF['topic_names'] = y_labels
    return genderDF


def get_male_female_topicsDF(data_dict, gender):
    """Return a DataFrame containing the per outlet topic distribution for a particular gender"""
    dataDF = pd.DataFrame.from_dict(data_dict[gender], orient='index')
    outlet_gender_topicsDF = pd.json_normalize(dataDF['topic_mean'])
    outlet_gender_topicsDF.index = dataDF.index
    outlet_gender_topicsDF = outlet_gender_topicsDF.sort_index()
    outlet_gender_topicsDF = outlet_gender_topicsDF.transpose()
    return outlet_gender_topicsDF


def construct_outlet_gender_DF(data_dict):
    """Convert the topic distribution per outlet and gender to a DataFrame representing the 
    difference between female/male source-dominant topics and reorder by magnitude
    """
    outlet_gender_dict = data_dict['perOutletGenderTopics']
    topics = data_dict['topics']
    male_outlet_topics = get_male_female_topicsDF(outlet_gender_dict, 'male')
    female_outlet_topics = get_male_female_topicsDF(outlet_gender_dict, 'female')
    # Plot the difference between the male-dominant and female-dominant topics
    diff = female_outlet_topics - male_outlet_topics
    # Calculate sum of all columns to decide sorting order
    diff['net'] = diff[diff.columns].sum(axis=1)
    diff = diff.sort_values('net').drop('net', axis=1)
    # Get a properly ordered list of topics based on prominence for axis labelling
    ordered_topics_dict = {idx: topics[idx] for idx in diff.index}
    ordered_names = [topics[idx]['name'] for idx in diff.index]
    top_5_words = get_top_n_words(ordered_topics_dict)
    # Get topic names for axis labels if they exist, otherwise return top-5 words per topic
    y_labels = [name if name else top_5_words[i] for i, name in enumerate(ordered_names)]
    return diff, y_labels


def construct_male_gender_df(data_dict):
    """Read the topic distribution per gender into a DataFrame and reorder by magnitude"""
    gender_dict = data_dict['perGenderTopics']
    topics = data_dict['topics']
    # Convert to Pandas DataFrame
    genderDF = pd.DataFrame.from_dict(gender_dict, orient='index').transpose()
    genderDF = genderDF[['female', 'male']]
    genderDF = genderDF.sort_values('male')
    genderDF['topic'] = [f"t{i}" for i in genderDF.index]

    # Get a properly ordered list of topics based on prominence for axis labelling
    ordered_topics_dict = {idx: topics[idx] for idx in genderDF.index}
    ordered_names = [topics[idx]['name'] for idx in genderDF.index]
    top_5_words = get_top_n_words(ordered_topics_dict)
    # Get topic names for axis labels if they exist, otherwise return top-5 words per topic
    y_labels = [name if name else top_5_words[i] for i, name in enumerate(ordered_names)]
    return genderDF, y_labels


def construct_female_gender_df(data_dict):
    """Read the topic distribution per gender into a DataFrame and reorder by importance"""
    gender_dict = data_dict['perGenderTopics']
    topics = data_dict['topics']
    # Convert to Pandas DataFrame
    genderDF = pd.DataFrame.from_dict(gender_dict, orient='index').transpose()
    genderDF = genderDF[['female', 'male']]
    genderDF = genderDF.sort_values('female')
    genderDF['topic'] = [f"t{i}" for i in genderDF.index]

    # Get a properly ordered list of topics based on prominence for axis labelling
    ordered_topics_dict = {idx: topics[idx] for idx in genderDF.index}
    ordered_names = [topics[idx]['name'] for idx in genderDF.index]
    top_5_words = get_top_n_words(ordered_topics_dict)
    # Get topic names for axis labels if they exist, otherwise return top-5 words per topic
    y_labels = [name if name else top_5_words[i] for i, name in enumerate(ordered_names)]
    return genderDF, y_labels


# ========== App Layout ================

def layout():
    """Dynamically serve a layout based on updated DB values (for dropdown menu)"""
    # Needs db connection! (Set up tunnel if testing app locally)
    _ids = get_doc_ids_from_db()   
    dropdown_dates = {num2str_month(_id): _id for _id in _ids}

    children_list = [
        html.Div([
            html.H2('Topic modelling'),
            dcc.Markdown(
                dangerously_allow_html=True,
                children=('''
                Our goal in this section is to analyze whether female and male sources are more likely
                to be associated with specific topics in the news. We utilize data scraped from six<sup>1</sup>
                Canadian news organizations' websites, following which we identify the gender of those
                quoted (sources). We then perform large-scale topic discovery on each month's data using
                Latent Dirichlet Allocation (LDA), as shown below.
            '''))],
        ),
        html.Div(html.Img(src="/static/topic-pipeline-flowchart-1.png", style={'width': '100%'})),
        html.P([
            html.Sup(1),
            '''Note that there were seven outlets between October 2018 and March 2021, after which HuffPost Canada stopped publishing.'''
        ], style={'font-size': '95%'},
        ),
        html.Br(),
        html.H5('Select month'),
        html.P('From the dropdown menu below, select a recent month to view its results.'),
        dcc.Dropdown(
            id='date-dropdown',
            options=[
                {'label': date_str, 'value': date_num}
                for date_str, date_num in dropdown_dates.items()
            ],
            value=_ids[-1],
            className='dropdown'
        ),
        html.Br(),
        html.Div(id='top15_datestring'),
        html.Div(
            DataTable(
                id='topic-table',
                columns=[
                    {'name': 'Topic labels', 'id': 'topic_names'},
                    {'name': 'Keywords', 'id': 'topic_words'},
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
        ),
        html.Br(),
        html.Div(
            dcc.Loading(
                id='topic-load-progress',
                children=[
                    dcc.Store(id='topic-data')
                ])
        ),
        # html.H4('Topics per outlet'),
        html.H5('''
            Which topics were covered more extensively by each outlet?
        '''),
        html.Div([dcc.Graph(id='outlet-heatmap')]),
        html.Div(html.Img(src="/static/topic-pipeline-flowchart-2.png", style={'width': '100%'})),
        dcc.Markdown('''
            Once we identify topics, we calculate an aggregated quantity that we call *gender prominence*,
            which is a measure that characterizes whether a given topic (on average) featured more
            prominently in articles that quote one gender more frequently than they do the other.
            
            To do this, we separate our news corpus for the given month into two smaller corpora - one 
            with articles that contain majority-female sources (at least one more female source than male),
            and the other with articles that contain majority-male sources. These corpora are termed the
            "female corpus" and "male corpus" respectively.
        '''),
        html.Br(),
        # html.H4('Topics and gender representation among sources'),
        html.H5('''
            Which topics showed the largest difference in gender representation?
        '''),
        html.Div(id='female-male-corpus-stats'),
        html.Div([
            dcc.Graph(id='outlet-gender-heatmap'),
            dcc.Markdown('''
                Topics that are red exhibit 'female prominence', i.e., they are topics
                for which the mean topic intensity is much greater in the female corpus than
                it is in the male corpus. The opposite is true for topics that exhibit 'male prominence'
                (shown in blue).
            '''),
            html.Br(),
            html.H5('''
                Which topics were covered more extensively in the female corpus?
            '''),
            html.Div(id='female-corpus-stats'),
            dcc.Graph(id='female-topic-bars'),
            html.Br(),
            html.H5('''
                Which topics were covered more extensively in the male corpus?
            '''),
            html.Div(id='male-corpus-stats'),
            dcc.Graph(id='male-topic-bars'),
            html.Br(),
        ]),
        html.Br(),
        dcc.Markdown('''
            [Click here](/static/GGT_topic_model_technical_report.pdf) to learn more about
            the Gender Gap Tracker's topic modelling methodology.
        '''),
    ]
    return children_list


# ========== Callbacks ================
@app.callback(Output('topic-data', 'data'), [Input('date-dropdown', 'value')])
def get_topic_data(value):
    with MongoClient(**MONGO_ARGS) as connection:
        read_collection = connection[READ_DB][READ_COL]
        data = read_collection.find({'_id': value})
        # Collect data
        data = list(data)[0]
    return data


@app.callback(Output('top15_datestring', 'children'),
              Input('date-dropdown', 'value'))
def display_top15_datestring(date_val):
    display_text = f"""
        Topic keywords for the top 15 topics in {num2str_month(date_val)}
    """
    return html.H5(display_text)


@app.callback(Output('female-male-corpus-stats', 'children'),
              [Input('topic-data', 'data'),
               Input('date-dropdown', 'value')])
def display_corpus_stats(data, date_val):
    female_corpus_size = data['params']['femaleDominantArticleCount']
    male_corpus_size = data['params']['maleDominantArticleCount']
    display_text = f"""
        In {num2str_month(date_val)}, there were {female_corpus_size:,} articles in the 
        female corpus, and {male_corpus_size:,} articles in the male corpus (across all outlets).
    """
    return dcc.Markdown(display_text)


@app.callback(Output('female-corpus-stats', 'children'),
              [Input('topic-data', 'data'),
               Input('date-dropdown', 'value')])
def display_female_corpus_stats(data, date_val):
    female_corpus_size = data['params']['femaleDominantArticleCount']
    display_text = f"""
        In {num2str_month(date_val)}, there were {female_corpus_size:,} articles in the 
        female corpus (across all outlets).
    """
    return dcc.Markdown(display_text)


@app.callback(Output('male-corpus-stats', 'children'),
              [Input('topic-data', 'data'),
               Input('date-dropdown', 'value')])
def display_male_corpus_stats(data, date_val):
    male_corpus_size = data['params']['maleDominantArticleCount']
    display_text = f"""
        In {num2str_month(date_val)}, there were {male_corpus_size:,} articles in the 
        male corpus (across all outlets).
    """
    return dcc.Markdown(display_text)


@app.callback(Output('update-dropdown', 'children'),
              [Input('interval-component', 'n_intervals')])
def update_dropdown(n, dropdown_val):
    _ids = get_doc_ids_from_db()    # Needs db connection! (Set up tunnel if testing app locally)
    dropdown_dates = {num2str_month(_id): _id for _id in _ids}
    return dcc.Dropdown(
        id='date-dropdown',
        options=[
            {'label': date_str, 'value': date_num}
            for date_str, date_num in dropdown_dates.items()
        ],
        value=_ids[-1],
    )


@app.callback(Output('topic-table', 'data'),
              [Input('topic-data', 'data')])
def get_topic_words(data):
    topic_words = get_top_n_words(data['topics'], n=15)
    topic_names = [topic['name'] for topic in data['topics'].values()]

    topic_dict = {}
    topic_dict['topic_names'] = topic_names
    topic_dict['topic_words'] = topic_words
    topicDF = pd.DataFrame.from_dict(topic_dict)
    # Sort by topic name for easier-to-read display
    topicDF = topicDF.sort_values(by='topic_names')
    output = topicDF.to_dict(orient='records')
    return output


@app.callback(Output('outlet-heatmap', 'figure'), [Input('topic-data', 'data')])
def update_heatmap(data):
    if data is None:
        return {'data': []}
    else:
        dff, y_labels = construct_outletDF(data)
        # Calculate chart width dynamically based on number of columns (uses a trendline obtained by trial & error)
        width = 35 * len(dff.columns.tolist()) + 493
        return {
            'data': [{
                'type': 'heatmap',
                'z': dff.values.tolist(),
                'y': y_labels,
                'x': dff.columns.tolist(),
                'xgap': 3,
                'ygap': 3,
                'colorscale': [
                    [0, 'rgb(255, 255, 255)'],
                    [1, '#006600']
                ],
                # 'colorscale': 'Greens',
                # 'reversescale': True,
                'showscale': True,
                'hovertemplate': '%{x}<br>%{y}<br>Mean topic weight: %{z:.3f}<extra></extra>',
                'colorbar': {
                    'x': 1.05,
                    'thickness': 25,
                    'len': 0.9,
                    'tickmode': 'array',
                    'tickvals': [min(dff.min()) + 0.02, max(dff.max()) - 0.02],
                    'ticktext': ['Weakly-covered<br>topics', 'Strongly-covered<br>topics']
                }
            }],
            'layout': {
                'font': {'size': 14},
                'height': 600,
                'width': width,
                'xaxis': {'side': 'top', 'gridcolor': 'rgba(0, 0, 0, 0)',
                          'tickangle': -35.0, 'ticks': 'outside'},
                'yaxis': {'side': 'left', 'gridcolor': 'rgba(0, 0, 0, 0)', 'ticks': 'outside'},
                'margin': {
                    'l': 350,
                    'r': 80,
                    't': 120,
                    'b': 30
                },
            }
        }


@app.callback(Output('outlet-gender-heatmap', 'figure'), [Input('topic-data', 'data')])
def update_gender_heatmap(data):
    if data is None:
        return {'data': []}
    else:
        dff, y_labels = construct_outlet_gender_DF(data)
        # Calculate chart width dynamically based on number of columns (uses a trendline obtained by trial & error)
        width = 35 * len(dff.columns.tolist()) + 467
        return {
            'data': [{
                'type': 'heatmap',
                'z': dff.values.tolist(),
                'y': y_labels,
                'x': dff.columns.tolist(),
                'xgap': 3,
                'ygap': 3,
                'colorscale': [
                    [0, 'rgb(0, 77, 114)'],
                    [0.5, 'rgb(255, 255, 255)'],
                    [1, 'rgb(175, 24, 88)']
                ],
                'zmid': 0,
                'zmin': -max(dff.max()),
                'zmax': max(dff.max()),
                'showscale': True,
                'hovertemplate': '%{x}<br>%{y}<br>Gender prominence: %{z:.3f}<extra></extra>',
                'colorbar': {
                    'x': 1.05,
                    'thickness': 25,
                    'len': 0.9,
                    'tickmode': 'array',
                    'tickvals': [-max(dff.max()) + 0.01, 0, max(dff.max()) - 0.01],
                    'ticktext': [
                        'Male<br>prominence',
                        'Neutral',
                        'Female<br>prominence']
                }
            }],
            'layout': {
                'font': {'size': 14},
                'height': 600,
                'width': width,
                'xaxis': {
                    'side': 'top', 'gridcolor': 'rgba(0, 0, 0, 0)',
                    'tickangle': -35.0, 'ticks': 'outside'
                },
                'yaxis': {
                    'side': 'left', 'gridcolor': 'rgba(0, 0, 0, 0)',
                    'ticks': 'outside'
                },
                'margin': {
                    'l': 350,
                    'r': 80,
                    't': 120,
                    'b': 30
                },
            }
        }


@app.callback(Output('female-topic-bars', 'figure'), [Input('topic-data', 'data')])
def update_female_gender_bars(data):
    if data is None:
        return {'data': []}
    else:
        dff, y_labels = construct_female_gender_df(data)
        top_val = max(max(dff['male']), max(dff['female']))
        return {
            'data': [
                {
                    'type': 'bar',
                    'orientation': 'h',
                    'x': dff.female.tolist(),
                    'y': y_labels,
                    'name': 'Female sources > male sources',
                    'marker': {'color': 'rgb(175, 24, 88)'},
                    'hovertemplate': 'Mean topic weight: %{x:.3f}<extra></extra>',
                },
            ],
            'layout': {
                # 'title': 'Topic dominance: articles where more women were quoted than men',
                'font': {'size': 14},
                'height': 600,
                'width': 700,
                'xaxis': {
                    'range': [0, top_val],
                    'title': 'Mean Topic weight',
                    'zeroline': True,
                    'zerolinecolor': 'rgb(200, 200, 200)',
                    'zerolinewidth': 2
                },
                'yaxis': {'zeroline': False, 'ticks': 'outside'},
                'legend': {'orientation': 'h', 'x': -1.0, 'y': 1.065},
                'margin': {
                    'l': 350,
                    'r': 100,
                    't': 50,
                    'b': 50
                },
            }
        }


@app.callback(Output('male-topic-bars', 'figure'), [Input('topic-data', 'data')])
def update_male_gender_bars(data):
    if data is None:
        return {'data': []}
    else:
        dff, y_labels = construct_male_gender_df(data)
        top_val = max(max(dff['male']), max(dff['female']))
        return {
            'data': [
                {
                    'type': 'bar',
                    'orientation': 'h',
                    'x': dff.male.tolist(),
                    'y': y_labels,
                    'name': 'Male sources > female sources',
                    'marker': {'color': 'rgb(0, 77, 114)'},
                    'hovertemplate': 'Mean topic weight: %{x:.3f}<extra></extra>',
                },
            ],
            'layout': {
                # 'title': 'Topic dominance: articles where more men were quoted than women',
                'font': {'size': 14},
                'height': 600,
                'width': 700,
                'xaxis': {
                    'range': [0, top_val],
                    'title': 'Mean Topic weight',
                    'zeroline': True,
                    'zerolinecolor': 'rgb(200, 200, 200)',
                    'zerolinewidth': 2
                },
                'yaxis': {'zeroline': False, 'ticks': 'outside'},
                'legend': {'orientation': 'h', 'x': -1.0, 'y': 1.065},
                'margin': {
                    'l': 350,
                    'r': 100,
                    't': 50,
                    'b': 50
                },
            }
        }
