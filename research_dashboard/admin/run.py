from dash import dcc, html
from dash.dependencies import Input, Output
from server import app, server
from apps import topiclabels, topsources, unknownsources, updatecache


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
        html.H2("Write to production database"),
        dcc.Markdown("""
            This is an admin dashboard that allows write access to our production MongoDB database 
            containing data from the Gender Gap Tracker. Any GUI-based services that allow a user to 
            write to the database can be included as a separate application through this dashboard
            structure. Extend the available functionality by adding new apps to button menu shown.

            Contact: Maite Taboada, [mtaboada@sfu.ca](mailto:mtaboada@sfu.ca)
            """
        ),
        html.P(['© 2021 ', html.A('Discourse Processing Lab.', href='https://www.sfu.ca/discourse-lab')],
            style={'font-size': '0.8em', 'color': '#a0a0a0'}
        )
    ])
]


def get_page_divs(page_layout):
    page = html.Div(children=[
        html.Div(
            children=[html.Table(
                html.Tr(
                    [html.Td(html.Img(src="/static/SFULogo.png", style={'padding': '10px 10px 5px 5px', 'height': '50px', 'width': '165px'}))] +
                    [html.Td(html.Img(src="/static/discourse-lab-logo.jpeg", style={'padding': '10px 10px 5px 5px', 'height': '100px', 'width': '165px'}))] +
                    [html.Td(html.H2("Measuring gender bias in media"))]
                )
            )], className='mainheader'),
        html.Br(),
        html.Div(
            children=[
                html.Div([
                    dcc.Link('Home', href='/'),
                    dcc.Link('Topic Model Labelling', href='/apps/topiclabels'),
                    dcc.Link('Top sources: Comments', href='/apps/topsources'),
                    dcc.Link('Unknown gender sources', href='/apps/unknownsources'),
                    dcc.Link('Update gender cache', href='/apps/updatecache'),
                ], className='menu')
            ]),
        html.Div(children=page_layout, className='main', style={'text-align': 'justify'}),
    ], className='container')
    return page


@app.callback(Output('page-content', 'children'),
              [Input('url', 'pathname')])
def display_page(pathname):
    if pathname == '/apps/topiclabels':
        return get_page_divs(topiclabels.layout())
    elif pathname == '/apps/topsources':
        return get_page_divs(topsources.layout())
    elif pathname == '/apps/unknownsources':
        return get_page_divs(unknownsources.layout())
    elif pathname == '/apps/updatecache':
        return get_page_divs(updatecache.layout()) 
    else:
        return get_page_divs(home_page)


if __name__ == '__main__':
    # app.run_server(host='0.0.0.0', port=8050, dev_tools_ui=False, threaded=True, debug=True)
    app.run_server(host='0.0.0.0', port=8050, debug=True)