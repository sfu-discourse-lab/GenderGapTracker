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
            This dashboard showcases results from our study on gender bias in the media via the 
            [Gender Gap Tracker (GGT)](https://gendergaptracker.informedopinions.org/), an automated system
            that measures men and women’s voices on
            seven major Canadian news outlets in real time. We analyze the rich information in news articles
            using Natural Language Processing (NLP) and quantify the discrepancy in proportions of men and
            women quoted. Our larger goals through this project are
            to enhance awareness of women’s portrayal in public discourse through hard evidence, and to 
            encourage news organizations to provide a more diverse set of voices in their reporting.

            The Gender Gap Tracker is a collaboration between [Informed Opinions](https://informedopinions.org/),
            a non-profit dedicated to amplifying women’s voices in media and Simon Fraser University, through
            the [Discourse Processing Lab] (https://www.sfu.ca/discourse-lab.html) and the
            [Big Data Initiative](https://www.sfu.ca/big-data/big-data-sfu).

            Multiple interactive applications are being implemented to explore the Gender Gap 
            Tracker's data. Click on the buttons shown on this page to access each application.

            Contact: Maite Taboada, [mtaboada@sfu.ca](mailto:mtaboada@sfu.ca)
            """
        ),
        html.P(['© 2020 ', html.A('Discourse Processing Lab', href='https://www.sfu.ca/discourse-lab')],
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
                    [html.Td(html.Div(html.P(['© 2020 Discourse Processing Lab.'])))]
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