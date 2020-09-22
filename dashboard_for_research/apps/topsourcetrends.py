import pandas as pd
from pymongo import MongoClient
# Dash
from dash.dependencies import Input, Output
import dash_core_components as dcc
import dash_html_components as html
import plotly.express as px
# Server and settings
from server import app, logger
from config import config

MONGO_ARGS = config['MONGO_ARGS']
READ_DB = config['DB']['SOURCES_DB']
READ_COL = config['DB']['SOURCES_TIME_SERIES_COL']


# ========== Functions ================

def get_time_series_from_db():
    """Read in time series statistics of top sources from MongoDB"""
    with MongoClient(**MONGO_ARGS) as connection:
        read_collection = connection[READ_DB][READ_COL]
        data = read_collection.find()
    return list(data)


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


def convert_date_to_pandas(data):
    """COnvert data (list of dicts) to Pandas DataFrame"""
    df = pd.DataFrame(data).drop('_id', axis=1).set_index('date')
    df['count'] = df['count'].astype(int)
    df = df.sort_values(by=['date', 'count'], ascending=[True, False])
    # Convert index to monthly period (we only perform aggregations on a monthly basis)
    df.index = df.index.to_period('M')
    return df


def filter_df(df, names):
    """Return a subset of the original DataFrame based on the user-input source names"""
    exists_name = df.name.isin(names)
    filtered = df[exists_name]
    return filtered


def pivot_df(df):
    """Pivot the existing DataFrame from long-form to wide-form for easy plotting
       We also pad zero-values for all months in which the source was not quoted.
    """
    pivoted = df.pivot(columns='name', values='count')
    # Define monthly range
    monthly_index = pd.period_range(start=df.index.min(), end=df.index.max(), freq='M')
    monthly_pivoted_df = pivoted.reindex(monthly_index).fillna(0)
    # Reformat index to month-year to make it easier to read in plots
    monthly_pivoted_df.index = monthly_pivoted_df.index.strftime('%b-%Y')
    return monthly_pivoted_df


def plot_lines(df):
    if not df.empty:
        fig = px.scatter(df, x=df.index, y=df.columns)
        fig.update_traces(mode="markers+lines", hovertemplate=None)
        fig.update_layout(hovermode="x", legend_title_text="", hoverlabel=dict(namelength=-1))
        fig['layout'].update(
            height=600,
            legend=dict(orientation='h', x=0.0, y=1.07, font=dict(size=15)),
            paper_bgcolor='rgba(0, 0, 0, 0)',
            plot_bgcolor='rgba(102, 204, 204, 0.05)',
            xaxis=dict(
                showgrid=True,
                zeroline=False,
                title_text='',
                automargin=True,
                tickangle=30,
                ticks='outside',
                gridcolor='rgb(240, 240, 240)',
            ),
            yaxis=dict(
                showgrid=True,
                zeroline=True,
                automargin=True,
                title_text='Number of times quoted',
                tickfont=dict(size=15),
                gridcolor='rgb(240, 240, 240)',
                zerolinecolor='rgba(240, 240, 240, 0.7)',
            ),
            margin=dict(l=20, r=20, t=50, b=30),
            modebar=dict(
                orientation='v',
                bgcolor='rgba(255, 255, 255, 0.7)',
            ),
        )
        return fig
    else:
        return {}


# ========== App Layout ================

def layout():
    """Dynamically serve a layout based on updated DB values (for multi-dropdown menu)"""
    # Needs db connection! (Set up tunnel if testing app locally)
    df = convert_date_to_pandas(get_time_series_from_db())
    # Clean up duplicate names (i.e., aliases that refer to the same person)
    df = df.replace({'name': get_aliases()})
    names = df.name.unique()

    children_list = [
        html.Div([
            html.H2('Monthly Trends'),
            dcc.Markdown('''
                In this section, we visualize monthly trends related to top-quoted sources.
                The example below shows how we observed a steep increase in the
                number of times Bonnie Henry (Provincial Health Officer of British Columbia) was
                quoted since the start of the COVID-19 pandemic. Interestingly, the number of times
                Theresa Tam (Canada's Chief Public Health Officer) was quoted dropped in June/July 2020, while
                Bonnie Henry's quote count remained high.

                To make a selection, begin by typing in a name into the menu below (autocomplete
                will detect similar names). Selections can be removed by clicking the 'x' button
                on a given name.
            '''),
            html.Div(
                dcc.Dropdown(
                    id='multi-dropdown',
                    options=[{'label': name, 'value': name} for name in names],
                    value=["Bonnie Henry", "Theresa Tam"],
                    multi=True,
                ),
                style={'padding': 5},
                className='custom-multi-dropdown',
            ),
            html.Div(
                dcc.Loading(
                    id='loading-progress',
                    children=[html.Div(dcc.Graph(id='line-chart'), className='chart')],
                ),
            ),
            dcc.Markdown('''
                The data shown in the line chart has been reduced to allow for faster response
                times. We only track the number of quotes for those people who appeared in the **top 50**
                female/male sources in any given month. As a result, only prominent, public-facing
                individuals are likely to feature in the drop-down selection menu.
            '''),
        ])
    ]
    return children_list


# ========== Callbacks ================

@app.callback(Output('line-chart', 'figure'), [Input('multi-dropdown', 'value')])
def get_line_plot(names):
    df = convert_date_to_pandas(get_time_series_from_db())
    df = df.replace({'name': get_aliases()})
    # Groupby common names in the same month
    df = df.groupby([df.index, 'name']).sum().reset_index(level=1)
    filtered = filter_df(df, names)
    try:
        pivoted = pivot_df(filtered)
        logger.info("Obtained DataFrame with unique name/count pairs.")
        fig = plot_lines(pivoted)
    except Exception as e:
        # Failsafe in case all values from dropdown are deleted
        fig = {}
        # logger.error("Monthly trends app error:", e)
    return fig
