import pandas as pd
from datetime import datetime, timedelta, date
from pymongo import MongoClient

# Dash
from dash.dependencies import Input, Output
from dash import dcc, html
import plotly.express as px

# Server and settings
from server import app, logger
from config import config

MONGO_ARGS = config["MONGO_ARGS"]
READ_DB = config["DB"]["SOURCES_DB"]
READ_COL = "mediaDaily"
ENGLISH_OUTLETS = config["ENGLISH_OUTLETS"]

# ========== Functions ================


def format_date(date_str):
    return datetime.strptime(date_str, "%Y-%m-%d")


def today():
    return datetime.today().date().strftime("%Y-%m-%d")


def get_female_proportions_df(outlets_list, begin_date, end_date):
    with MongoClient(**MONGO_ARGS) as connection:
        collection = connection[READ_DB][READ_COL]
        data = collection.aggregate(
            [
                {
                    "$match": {
                        "outlet": {"$in": outlets_list},
                        "publishedAt": {
                            "$gte": begin_date,
                            "$lt": end_date,
                        },
                    }
                },
                {
                    "$project": {
                        "_id": 0,
                        "outlet": 1,
                        "publishedAt": 1,
                        "totalArticles": 1,
                        "totalFemales": 1,
                        "totalMales": 1,
                        "totalUnknowns": 1,
                    }
                },
            ]
        )
        df = pd.DataFrame(list(data))
        df["publishedAt"] = pd.to_datetime(df["publishedAt"])
        df["female_proportion"] = (
            100 * df["totalFemales"] / (df["totalMales"] + df["totalFemales"] + df["totalUnknowns"])
        )
        df = (
            df.drop(["totalArticles", "totalFemales", "totalMales", "totalUnknowns"], axis=1)
            .sort_values(by=["publishedAt", "outlet"], ascending=[True, True])
            .drop_duplicates(subset=["publishedAt", "outlet"])
        )
        df = (
            df.set_index(['publishedAt', 'outlet'])
            .unstack(fill_value=0)
            .asfreq('D', fill_value=0)
            .stack()
            .sort_index(level=1)
            .reset_index()
            .set_index('publishedAt')
        )
        # Rolling average
        df["rolling_avg"] = (
            df["female_proportion"]
            .rolling(7, min_periods=1)
            .mean()
        )
    return df


def plot_lines(df, outlet_name):
    assert "outlet" in df.columns
    assert "rolling_avg" in df.columns
    dff = df.loc[df["outlet"] == outlet_name]
    if not dff.empty:
        fig = px.scatter(
            dff,
            x=dff.index,
            y="rolling_avg",
            trendline="ols",
            trendline_color_override="pink",
        )
        fig.update_traces(
            mode="lines",
            hovertemplate='%{y:.1f}%<extra></extra>',
        )
        fig.update_layout(
            hovermode="x unified",
            legend_title_text="",
            hoverlabel=dict(
                namelength=-1,
                bgcolor="white",
            ),
        )
        fig["layout"].update(
            height=300,
            legend=dict(font=dict(size=15)),
            paper_bgcolor="rgba(0, 0, 0, 0)",
            plot_bgcolor="rgba(102, 204, 204, 0.05)",
            xaxis=dict(
                showgrid=True,
                zeroline=False,
                title_text="",
                automargin=True,
                tickangle=30,
                ticks="outside",
                tickmode="auto",
                gridcolor="rgb(240, 240, 240)",
                type="date",
            ),
            yaxis=dict(
                showgrid=True,
                zeroline=True,
                automargin=True,
                title_text="Proportion of women quoted (%)",
                tickfont=dict(size=15),
                gridcolor="rgb(240, 240, 240)",
                zerolinecolor="rgba(240, 240, 240, 0.7)",
            ),
            margin=dict(l=20, r=20, t=50, b=30),
            modebar=dict(
                orientation="v",
                bgcolor="rgba(255, 255, 255, 0.7)",
            ),
        ),
        fig.update_yaxes(range=[0.0, 60.0])
        # Ensure we don't crowd the x-axis with too many ticklabels
        fig.update_xaxes(nticks=12)
        return fig
    else:
        return {}


# ========== App Layout ================


def layout():
    """Dynamically serve a layout based on updated DB values"""
    children_list = [
        html.Div(
            [
                html.H2("Daily proportion of women quoted"),
                html.Div(
                    dcc.Markdown(
                        """
                        The below charts showcase a 7-day moving average of the daily
                        proportion of women quoted for each outlet since October 2018.
                        The pink line indicates the linear trendline over this period.
                        """
                    ),
                ),
                html.Br(),
                dcc.Markdown("Select a start and end date from the widget below."),
                html.Div(
                    dcc.DatePickerRange(
                        id='date-picker-range',
                        min_date_allowed=date(2018, 10, 1),
                        max_date_allowed=datetime.today().date() - timedelta(days=1),
                        start_date=date(2018, 10, 1),
                        end_date=datetime.today().date() - timedelta(days=1),
                        initial_visible_month=datetime.today().date(),
                    ),
                ),
                dcc.Store(id='stored-df-data'),
                html.Br(),
                html.H5("CBC News"),
                html.Div(
                    dcc.Loading(
                        id="loading-progress-1",
                        children=[
                            html.Div(
                                dcc.Graph(id="cbc-news-graph"),
                                className="chart",
                            )
                        ],
                    ),
                ),
                html.H5("CTV News"),
                html.Div(
                    dcc.Loading(
                        id="loading-progress-2",
                        children=[
                            html.Div(
                                dcc.Graph(id="ctv-news-graph"),
                                className="chart",
                            )
                        ],
                    ),
                ),
                html.H5("Global News"),
                html.Div(
                    dcc.Loading(
                        id="loading-progress-3",
                        children=[
                            html.Div(
                                dcc.Graph(id="global-news-graph"),
                                className="chart",
                            )
                        ],
                    ),
                ),
                html.H5("Huffington Post"),
                dcc.Markdown(
                    """
                    HuffPost Canada stopped publishing as of March 2021, so we
                    see the total number of articles for HuffPost drop to zero after
                    this period.
                    """
                ),
                html.Div(
                    dcc.Loading(
                        id="loading-progress-4",
                        children=[
                            html.Div(
                                dcc.Graph(id="huffington-post-graph"),
                                className="chart",
                            )
                        ],
                    ),
                ),
                html.H5("National Post"),
                html.Div(
                    dcc.Loading(
                        id="loading-progress-5",
                        children=[
                            html.Div(
                                dcc.Graph(id="national-post-graph"),
                                className="chart",
                            )
                        ],
                    ),
                ),
                html.H5("The Globe And Mail"),
                html.Div(
                    dcc.Loading(
                        id="loading-progress-6",
                        children=[
                            html.Div(
                                dcc.Graph(id="globe-and-mail-graph"),
                                className="chart",
                            )
                        ],
                    ),
                ),
                html.H5("The Toronto Star"),
                html.Div(
                    dcc.Loading(
                        id="loading-progress-7",
                        children=[
                            html.Div(
                                dcc.Graph(id="the-toronto-star-graph"),
                                className="chart",
                            )
                        ],
                    ),
                ),
            ]
        )
    ]
    return children_list


# ========== Callbacks ================

@app.callback(
    Output('stored-df-data', 'data'),
    Input('date-picker-range', 'start_date'),
    Input('date-picker-range', 'end_date'))
def clean_data(begin_date, end_date):
    begin_date = format_date(begin_date)
    end_date = format_date(end_date)
    # Precompute the aggregated dataframe with female proportions just once
    df = get_female_proportions_df(ENGLISH_OUTLETS, begin_date, end_date)
    return df.to_json(date_format='iso', orient='split')


@app.callback(
    Output('cbc-news-graph', 'figure'),
    Input('stored-df-data', 'data'), prevent_initial_call=True)
def update_fig_1(jsonified_cleaned_data):
    df = pd.read_json(jsonified_cleaned_data, orient='split')
    return plot_lines(df, "CBC News")


@app.callback(
    Output('ctv-news-graph', 'figure'),
    Input('stored-df-data', 'data'), prevent_initial_call=True)
def update_fig_2(jsonified_cleaned_data):
    df = pd.read_json(jsonified_cleaned_data, orient='split')
    return plot_lines(df, "CTV News")


@app.callback(
    Output('global-news-graph', 'figure'),
    Input('stored-df-data', 'data'), prevent_initial_call=True)
def update_fig_3(jsonified_cleaned_data):
    df = pd.read_json(jsonified_cleaned_data, orient='split')
    return plot_lines(df, "Global News")


@app.callback(
    Output('huffington-post-graph', 'figure'),
    Input('stored-df-data', 'data'), prevent_initial_call=True)
def update_fig_4(jsonified_cleaned_data):
    df = pd.read_json(jsonified_cleaned_data, orient='split')
    return plot_lines(df, "Huffington Post")


@app.callback(
    Output('national-post-graph', 'figure'),
    Input('stored-df-data', 'data'), prevent_initial_call=True)
def update_fig_5(jsonified_cleaned_data):
    df = pd.read_json(jsonified_cleaned_data, orient='split')
    return plot_lines(df, "National Post")


@app.callback(
    Output('globe-and-mail-graph', 'figure'),
    Input('stored-df-data', 'data'), prevent_initial_call=True)
def update_fig_6(jsonified_cleaned_data):
    df = pd.read_json(jsonified_cleaned_data, orient='split')
    return plot_lines(df, "The Globe And Mail")


@app.callback(
    Output('the-toronto-star-graph', 'figure'),
    Input('stored-df-data', 'data'), prevent_initial_call=True)
def update_fig_7(jsonified_cleaned_data):
    df = pd.read_json(jsonified_cleaned_data, orient='split')
    return plot_lines(df, "The Star")
