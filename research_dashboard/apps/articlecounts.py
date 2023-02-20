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
READ_COL = "articleCountsDaily"
ENGLISH_OUTLETS = config["ENGLISH_OUTLETS"]
FRENCH_OUTLETS = config["FRENCH_OUTLETS"]


# ========== Functions ================


def format_date(date_str):
    return datetime.strptime(date_str, "%Y-%m-%d")


def last_6_months():
    today = datetime.today().date() - timedelta(days=180)
    return today.strftime("%Y-%m-%d")


def today():
    return datetime.today().date().strftime("%Y-%m-%d")


def get_article_counts_from_db(outlets_list, begin_date, end_date):
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
                    }
                },
            ]
        )
        counts_df = pd.DataFrame(list(data))
        counts_df["publishedAt"] = pd.to_datetime(counts_df["publishedAt"])
        counts_df.set_index("publishedAt", inplace=True)
        counts_df = counts_df.sort_index()
    return counts_df


def get_line_plot_for_articles(outlets, start_date, end_date):
    df = get_article_counts_from_db(outlets, start_date, end_date)
    # Group by outlets, resample weekly, and set index as date
    df_resampled = (
        df.groupby('outlet')
        .resample('W')
        .sum()
        .reset_index()
    )
    # Complicated way to fill in zero values for missing dates while also keeping outlet names
    # Adapted from: https://stackoverflow.com/a/44979696/1194761 
    df_resampled = (
        df_resampled
        .set_index(['publishedAt', 'outlet'])
        .unstack(fill_value=0)
        .asfreq('W', fill_value=0)
        .stack()
        .sort_index(level=1)
        .reset_index()
        .set_index('publishedAt')
    )
    # Make sure plotting is only done on dates prior to today
    todays_date = pd.to_datetime(datetime.today().date())
    df_range = (
        df_resampled.loc[df_resampled.index <= todays_date]
    )
    fig = plot_lines(df_range)
    return fig


def plot_lines(df):
    assert "totalArticles" in df.columns
    assert "outlet" in df.columns
    if not df.empty:
        fig = px.line(df, x=df.index, y="totalArticles", color="outlet")
        fig.update_traces(mode="lines", hovertemplate=None)
        fig.update_layout(
            hovermode="x unified",
            legend_title_text="",
            hoverlabel=dict(namelength=-1),
        )
        fig["layout"].update(
            height=600,
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
                rangeselector=dict(
                    buttons=list(
                        [
                            dict(
                                count=1, label="1m", step="month", stepmode="backward"
                            ),
                            dict(
                                count=3, label="3m", step="month", stepmode="backward"
                            ),
                            dict(
                                count=6, label="6m", step="month", stepmode="backward"
                            ),
                        ]
                    ),
                ),
                rangeslider=dict(visible=False),
                type="date",
            ),
            yaxis=dict(
                showgrid=True,
                zeroline=True,
                automargin=True,
                title_text="Number of articles",
                tickfont=dict(size=15),
                gridcolor="rgb(240, 240, 240)",
                zerolinecolor="rgba(240, 240, 240, 0.7)",
            ),
            margin=dict(l=20, r=20, t=50, b=30),
            modebar=dict(
                orientation="v",
                bgcolor="rgba(255, 255, 255, 0.7)",
            ),
        )
        # Ensure we don't crowd the x-axis with too many ticklabels
        fig.update_xaxes(nticks=10)
        return fig
    else:
        return {}


# ========== App Layout ================


def layout():
    """Dynamically serve a layout based on updated DB values"""
    children_list = [
        html.Div(
            [
                html.H2("Weekly article counts per outlet"),
                html.Div(
                    dcc.Markdown(
                        """
                        This section showcases the weekly article counts for the
                        articles we scraped from the various English and French outlets.
                        To see the data across different time periods (1, 3, or 6
                        months), click on the buttons labelled `1m`, `3m` and `6m`. Note
                        that double-clicking each item on the legend at the right of the
                        chart isolates the chart to only that outlet, while
                        double-clicking on an item for the **second** time resets the
                        chart to show all outlets' data once again. Single-clicking an
                        item on the legend hides its data from the chart.
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
                        start_date=datetime.today().date() - timedelta(days=180),
                        end_date=datetime.today().date() - timedelta(days=1),
                        initial_visible_month=datetime.today().date(),
                    ),
                ),
                html.Br(),
                html.H4("English outlets"),
                dcc.Markdown(
                    """
                    The chart below shows the weekly sum of articles scraped from each
                    English outlet. The date value displayed on the X-axis indicates the
                    ending day (Sunday) of the preceding week in which the articles were
                    scraped.
                    """
                ),
                html.Div(
                    dcc.Loading(
                        id="loading-progress-1",
                        children=[
                            html.Div(
                                dcc.Graph(
                                    id='output-container-english-fig'
                                ),
                                className="chart",
                            )
                        ],
                    ),
                ),
                html.H4("French outlets"),
                dcc.Markdown(
                    """
                    The chart below shows the weekly sum of articles scraped from each
                    French outlet. Just as in the previous chart, the date value
                    displayed on the X-axis indicates the ending day (Sunday) of the
                    preceding week in which the articles were scraped.
                    """
                ),
                html.Div(
                    dcc.Loading(
                        id="loading-progress-2",
                        children=[
                            html.Div(
                                dcc.Graph(
                                    id='output-container-french-fig'
                                ),
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
    Output('output-container-english-fig', 'figure'),
    Input('date-picker-range', 'start_date'),
    Input('date-picker-range', 'end_date'))
def update_fig_english(start_date, end_date):
    if not start_date:
        start_date = format_date(last_6_months())
    if not end_date:
        end_date = format_date(today()) + timedelta(days=1)
    try:
        fig = get_line_plot_for_articles(
            ENGLISH_OUTLETS,
            format_date(start_date),
            format_date(end_date),
        )
    except:
        fig = {}
    return fig


@app.callback(
    Output('output-container-french-fig', 'figure'),
    Input('date-picker-range', 'start_date'),
    Input('date-picker-range', 'end_date'))
def update_fig_french(start_date, end_date):
    if not start_date:
        start_date = format_date(last_6_months())
    if not end_date:
        end_date = format_date(today()) + timedelta(days=1)
    try:
        fig = get_line_plot_for_articles(
            FRENCH_OUTLETS,
            format_date(start_date),
            format_date(end_date),
        )
    except:
        fig = {}
    return fig
