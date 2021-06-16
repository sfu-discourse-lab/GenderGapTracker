from datetime import datetime
import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Input, Output

from server import app, server
from apps import textanalyzer, topicmodel, topsources, topsourcetrends

box_style = {
    'padding': '10px 10px 5px 5px',
    'marginLeft': 'auto', 'marginRight': 'auto',
}

# Define the main app's layout
app.layout = html.Div([
    dcc.Location(id='url', refresh=False),
    html.Div(id='page-content')
])

# Layout for text on home page
home_page = [
    html.Div(children=[
        html.Br(),
        dcc.Markdown("""
            This research dashboard showcases results from our study on gender bias in the media. 
            We present the [Gender Gap Tracker (GGT)](https://gendergaptracker.informedopinions.org/), 
            an automated system that measures men and women’s voices on seven major Canadian news outlets in real time. 
            We analyze the rich information in news articles using Natural Language Processing (NLP) and quantify the 
            discrepancy in proportions of men and women quoted. Our larger goals through this project are to enhance 
            awareness of women’s portrayal in public discourse through hard evidence, and to encourage news 
            organizations to provide a more diverse set of voices in their reporting.

            The Gender Gap Tracker is a collaboration between [Informed Opinions](https://informedopinions.org/),
            a non-profit dedicated to amplifying women’s voices in media and Simon Fraser University, through
            the [Discourse Processing Lab] (https://www.sfu.ca/discourse-lab.html) and the
            [Big Data Initiative](https://www.sfu.ca/big-data/big-data-sfu).

            See our peer-reviewed publications for more detailed technical information on our methodology:  
              
            1. Asr FT, Mazraeh M, Lopes A, Gautam V, Gonzales J, Rao P, Taboada M. (2021) 
            The Gender Gap Tracker: Using Natural Language Processing to measure gender bias in media. 
            *PLoS ONE 16(1)*:e0245533. https://doi.org/10.1371/journal.pone.0245533  
            2. Rao P, Taboada M. (2021), Gender bias in the news: A scalable topic modelling and visualization
            framework. *Frontiers Artif. Intell.* https://doi.org/10.3389/frai.2021.664737

            All of our code for scraping, NLP, topic modelling and data visualization is publicly available on GitHub
            so that others can benefit from the methodology:  
            https://github.com/sfu-discourse-lab/GenderGapTracker

            For more information about the research methodology and for questions regarding collaboration, 
            please contact Maite Taboada at [mtaboada@sfu.ca](mailto:mtaboada@sfu.ca).
            """
        ),
        html.P(['© 2021 ', html.A('Discourse Processing Lab', href='https://www.sfu.ca/discourse-lab')],
            style={'font-size': '0.8em', 'color': '#a0a0a0'}
        )
    ])
]


def get_page_divs(page_layout, enable_footer=True):
    page = html.Div(children=[
        html.Div(
            children=[html.Table(
                html.Tr(
                    [html.Td(html.Img(src="/static/SFULogo.png", style={'padding': '10px 10px 5px 5px', 'height': '50px', 'width': '165px'}))] +
                    [html.Td(html.Img(src="/static/discourse-lab-logo.jpeg", style={'padding': '10px 10px 5px 5px', 'height': '100px', 'width': '165px'}))] +
                    [html.Td(html.H3("Measuring gender bias in media"))]
                )
            )], className='mainheader'),
        html.Br(),
        html.Div(
            children=[
                html.Div([
                    dcc.Link('Home', href='/'),
                    dcc.Link('Text analyzer', href='/apps/textanalyzer'),
                    dcc.Link('Topic models', href='/apps/topicmodel'),
                    dcc.Link('Top-quoted sources', href='/apps/topsources'),
                    dcc.Link('Monthly trends', href='/apps/topsourcetrends'),
                ], className='menu')
            ]),
        html.Div(children=page_layout, className='main'),
        html.Div(children=case_footer(enable_footer))
    ], className='container')
    return page


def case_footer(enable_footer):
    if enable_footer:
        footer = html.Div(
            children=[html.Table(
                html.Tr(
                    [html.Td(html.Img(src="/static/SFULogo.png", style={'height': '30px', 'width': '120px'}))] +
                    [html.Td(html.Img(src="/static/discourse-lab-logo.jpeg", style={'height': '60px', 'width': '100px'}))] +
                    [html.Td(html.Div(html.P([f"© {datetime.today().year} Discourse Processing Lab."])))]
                )
            )
        ], className='mainfooter'),
    else:
        footer = html.Div([])
    return footer


@app.callback(Output('page-content', 'children'),
              [Input('url', 'pathname')])
def display_page(pathname):
    if pathname == '/apps/textanalyzer':
        return get_page_divs(textanalyzer.layout())
    elif pathname == '/apps/topicmodel':
        return get_page_divs(topicmodel.layout())
    elif pathname == '/apps/topsources':
        return get_page_divs(topsources.layout())
    elif pathname == '/apps/topsourcetrends':
        return get_page_divs(topsourcetrends.layout())
    else:
        return get_page_divs(home_page, enable_footer=False)


if __name__ == '__main__':
    app.run_server(host='0.0.0.0', port=8050, debug=True)