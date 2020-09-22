import datetime
import pandas as pd
from pymongo import MongoClient
# Dash
import dash_html_components as html
import dash_core_components as dcc
from dash.dependencies import Input, Output
import plotly.graph_objs as go
# Server and settings
from server import app, logger
from config import config

MONGO_ARGS = config['MONGO_ARGS']
READ_DB = config['DB']['READ_DB']
READ_COL = config['DB']['READ_COL']
SOURCES_DB = config['DB']['SOURCES_DB']
SOURCES_COL = config['DB']['SOURCES_COL']
NUM_SOURCES_TO_SHOW = 15


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


def get_aliases(txtfile='aliases.txt'):
    """Prepare a dictionary that is used to replace aliases with a standard version
       of a name. For example, 'Queen Elizabeth' is replaced with the official name,
       'Queen Elizabeth II'.
    """
    alias_dict = {}
    with open(txtfile) as f:
        next(f)   # Skip header
        for line in f:
            names = line.strip().split(',')
            for name in names[1:]:
                # Aliases are defined in the text file as the second name onwards
                alias_dict[name.strip()] = names[0]
    return alias_dict


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


def get_sources_dataframe(stats):
    """Convert JSON object of top sources to pandas DataFrame"""
    top_females = pd.DataFrame(stats['topFemaleSources'])
    # Clean up duplicate names (i.e., aliases that refer to the same person)
    top_females = top_females.replace({'name': get_aliases()})
    # Groupby common names in the same month
    top_females = top_females.groupby('name').sum().sort_values(by='count', ascending=False).reset_index()

    top_males = pd.DataFrame(stats['topMaleSources'])
    # Clean up duplicate names (i.e., aliases that refer to the same person)
    top_males = top_males.replace({'name': get_aliases()})
    # Groupby common names in the same month
    top_males = top_males.groupby('name').sum().sort_values(by='count', ascending=False).reset_index()
    
    # Add a column indicating male or female status
    top_females['gender'] = 'F'
    top_males['gender'] = 'M'
    # Ensure that source counts are stored as ints
    top_females['count'] = top_females['count'].astype('int')
    top_males['count'] = top_males['count'].astype('int')

    # Next, we set the limit on the length of female/male dataframes for plotting
    # We sort once again in ascending order to place the items in the right order for the plot
    top_females = top_females.iloc[:NUM_SOURCES_TO_SHOW, :].sort_values(by='count')
    top_males = top_males.iloc[:NUM_SOURCES_TO_SHOW, :].sort_values(by='count')
    # Merge the female and male dataframes for a single comparative dot plot
    df = pd.concat((top_females, top_males), axis=0)
    df.columns = ['name', 'count', 'gender']
    return df


def get_lollipop_plot(stats):
    """Create pie chart subplot figure objects for dash"""
    # df = get_sources_dataframe(stats, limit=set_limit)
    df = get_sources_dataframe(stats)
    minval, maxval = df['count'].min(), df['count'].max()
    # Separate into female and male dataframes
    female_df = df[df['gender'] == 'F'].reset_index()
    male_df = df[df['gender'] == 'M'].reset_index()
    logger.info(f"Top sources: Obtained female dataframe of length {len(female_df)} "
                f"and male dataframe of length {len(male_df)}.")
    # Female dots
    data1 = go.Scatter(
        x=female_df['count'],
        y=female_df.index,
        text=female_df['name'],
        mode='markers+text',
        textposition='bottom left',
        cliponaxis=False,
        marker=dict(size=10, color='rgb(175, 24, 88)'),
        hoverinfo='x+text',
        hovertemplate='%{text}<br>%{x} quotes<extra></extra>',
        name='Female sources',
    )
    # Male dots
    data2 = go.Scatter(
        x=male_df['count'],
        y=male_df.index,
        text=male_df['name'],
        mode='markers+text',
        textposition='top right',
        cliponaxis=False,
        marker=dict(size=10, color='rgb(0, 77, 114)'),
        hoverinfo='x+text',
        hovertemplate='%{text}<br>%{x} quotes<extra></extra>',
        name='Male sources',
    )
    # Horizontal line connector
    shapes = [dict(
        type='line',
        x0=female_df['count'].loc[i],
        y0=female_df.index[i],
        x1=male_df['count'].loc[i],
        y1=male_df.index[i],
        layer='below',
        line=dict(
            color='rgb(200, 200, 200)',
            width=2
        )) 
        for i in range(len(female_df))
    ]
    # Pass shapes to layout
    layout = go.Layout(shapes=shapes)

    # Figure object settings
    fig = go.Figure([data1, data2], layout)
    fig['layout'].update(
        height=40 * NUM_SOURCES_TO_SHOW + 200,
        # width=900,
        legend=dict(orientation='h', x=0.27, y=1.07, font=dict(size=15)),
        paper_bgcolor='rgba(0, 0, 0, 0)',
        plot_bgcolor='rgba(102, 204, 204, 0.05)',
        xaxis=dict(
            showgrid=True,
            zeroline=True,
            title_text='# Articles in which quoted',
            range=[minval - 100, maxval + 100],
            ticks='outside',
            tickfont=dict(size=18),
            automargin=True,
            gridcolor='rgb(240, 240, 240)',
            zerolinecolor='rgba(240, 240, 240, 0.7)',
        ),
        yaxis=dict(
            showgrid=False,
            zeroline=False,
            automargin=True,
            showticklabels=False
        ),
        margin=dict(l=80, r=80, t=30, b=30),
        modebar=dict(
            orientation='v',
            bgcolor='rgba(255, 255, 255, 0.7)',
        ),
    )
    return fig


# ========== App Layout ================

def layout():
    """Dynamically serve a layout based on updated DB values (for dropdown menu)"""
    # Needs db connection! (Set up tunnel if testing app locally)
    _ids = get_doc_ids_from_db()   
    dropdown_dates = {num2str_month(_id): _id for _id in _ids}

    children_list = [
        html.Div([
            html.H2('Top-quoted female and male sources'),
            html.P('''
                In this section, we display the top-quoted sources from either gender. Select
                a month from the dropdown menu below to view its results.
            ''')],
        ),
        html.Br(),
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
        html.Div(
            dcc.Loading(
                id='topic-load-progress',
                children=[
                    dcc.Store(id='top-sources-topic-data'),
                    dcc.Store(id='top-sources-stats'),
                ])
        ),
        html.Br(),
        html.H4('Topics and gender representation among sources'),
        dcc.Markdown('''
            First, we display the *gender prominence* for each topic discovered in the 
            given month. Gender prominence is a measure we use to study whether a
            given topic features quotes by men or women more prominently.
        '''),
        html.Div([
            dcc.Graph(id='top-sources-outlet-gender-heatmap'),
        ]),
        html.Br(),
        html.Div([
            html.H4('Top quoted sources by gender'),
            html.P(f'''
                Next, we display the top {NUM_SOURCES_TO_SHOW} sources per gender for the given month.
                Hover over the dots to display the total number of articles in which each source was 
                quoted.
            '''),
            html.Div([
                dcc.Graph(id='top-sources-dotplot', className='chart'),
            ]),
        ]),
        html.H4('Observations'),
        dcc.Markdown(id='user-comment-display'),
    ]
    return children_list


# ========== Callbacks ================

@app.callback(Output('top-sources-topic-data', 'data'), [Input('date-dropdown', 'value')])
def get_topic_data(value):
    with MongoClient(**MONGO_ARGS) as connection:
        read_collection = connection[READ_DB][READ_COL]
        data = read_collection.find({'_id': value})
        # Collect data
        data = list(data)[0]
    return data


@app.callback(Output('top-sources-stats', 'data'), [Input('date-dropdown', 'value')])
def get_monthly_stats(value):
    with MongoClient(**MONGO_ARGS) as connection:
        read_collection = connection[SOURCES_DB][SOURCES_COL]
        stats = read_collection.find({'_id': value})
        # Collect top sources stats
        stats = list(stats)[0]
    return stats


@app.callback(Output("top-sources-dotplot", "figure"), [Input('top-sources-stats', 'data')])
def update_top_sources_lollipop(data):
    """Update lollipop charts with female/male top sources"""
    try:
        fig = get_lollipop_plot(data)
    except Exception as e:
        # Failsafe in case all values from dropdown are deleted
        fig = {}
        # logger.error("Top sources app error:", e)
    return fig 


@app.callback(Output("user-comment-display", "children"), [Input('top-sources-stats', 'data')])
def collect_user_comments(data):
    """Display user-comments"""
    return data['comment']


@app.callback(Output('top-sources-update-dropdown', 'children'),
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


@app.callback(Output('top-sources-outlet-gender-heatmap', 'figure'), [Input('top-sources-topic-data', 'data')])
def update_gender_heatmap(data):
    if data is None:
        return {'data': []}
    else:
        dff, y_labels = construct_outlet_gender_DF(data)
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
                'width': 710,
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
                'modebar': {
                    'orientation': 'h',
                    'bgcolor': 'rgba(255, 255, 255, 0.7)',
                },
            }
        }
