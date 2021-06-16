# Research Dashboard

- [Research Dashboard](#research-dashboard)
  - [Background](#background)
  - [Password-protection for write dashboard](#password-protection-for-write-dashboard)
  - [Installation](#installation)
      - [spaCy language models](#spacy-language-models)
  - [Pre-requisites](#pre-requisites)
      - [Gender prediction service](#gender-prediction-service)
      - [MongoDB database connection](#mongodb-database-connection)
    - [Run development server](#run-development-server)
  - [Deployment](#deployment)
    - [Update to the latest code version](#update-to-the-latest-code-version)
    - [Restart the server](#restart-the-server)
  - [Update `aliases.txt` file](#update-aliasestxt-file)
      - [Ensure Dash is serving custom JS locally](#ensure-dash-is-serving-custom-js-locally)
  - [Troubleshooting](#troubleshooting)
  - [Dashboard Design & Structure](#dashboard-design--structure)
    - [Multi-page dashboard](#multi-page-dashboard)
      - [Root directory](#root-directory)
      - [Apps](#apps)
      - [Assets](#assets)
      - [Static](#static)
  - [Application code - readability guidelines](#application-code---readability-guidelines)
    - [1. App layout](#1-app-layout)
    - [2. Callbacks](#2-callbacks)
    - [3. Custom functions](#3-custom-functions)
  - [Additional tips](#additional-tips)
    - [Limit the size of JSON objects being transferred](#limit-the-size-of-json-objects-being-transferred)
    - [Sharing data between callbacks](#sharing-data-between-callbacks)


---
## Background
This page contains code for dashboard apps that we are building internally in the discourse processing lab, pertaining to the Gender Gap Tracker. To speed up development and experimentation, the [Plotly Dash](https://dash.plotly.com/) framework is used. Dash is a web application framework built on top of Flask, Plotly.js and React.js that greatly increases the ease with which reactive interfaces can be built, without requiring users to write JavaScript code (all code in this repo is written in Python).

There are two main dashboards deployed and described in this README:
* **Read** dashboard: displays results that are read from our MongoDB database. The URL for the read dashboard is [gendergaptracker.research.sfu.ca/](gendergaptracker.research.sfu.ca/).
* **Write** dashboard: allows a user to write data directly to the database using an interactive UI. The URL for the write dashboard is [admin.gendergaptracker.research.sfu.ca/](gendergaptracker.research.sfu.ca/).


## Password-protection for write dashboard
The write dashboard is deployed as an admin page with password protection - this is mainly because exposing write-functionality on a public URL to unprivileged users can be a serious security risk. All code for the write-dashboard is separated from the read dashboard, in the [admin](https://github.com/maitetaboada/WomenInMedia/tree/master/dashboard_for_research/admin) directory.


## Installation
First, set up a virtual environment and install the dependencies from requirements.txt:

```sh
python3 -m venv GRIM-3
source GRIM-3/bin/activate
pip3 install -r requirements.txt
```

#### spaCy language models
We also need the spaCy language models installed for the NLP functions. Both the small and language models are installed, depending on the requirement.

```sh
python3 -m spacy download en_core_web_sm
python3 -m spacy download en_core_web_lg
```

## Pre-requisites

#### Gender prediction service
The Dash app requires that our gender prediction Flask service (deployed as part of the GGT) is already running in the background and is serving gender results on port 5000. To make it easier to update and deploy, we define it as a system service that can be started/restarted using the below commands (**NOTE:** this requires sudo privileges).

```sh
sudo service gender_recognition start
sudo service gender_recognition restart
```

#### MongoDB database connection
All our data for the GGT is hosted on a MongoDB database. Both the read and write dashboards must be run on a machine that has an ssh tunnel to the database set up - this allows us to pass data back and forth from MongoDB to the dashboard's UI as required.

### Run development server
During development, run the dash app locally (after starting the gender recognition Flask server and setting up a tunnel to the database) as follows:

```sh
python3 run.py
```

## Deployment
The app is deployed using `nginx` (for load balancing incoming HTTP traffic) and `gunicorn` (to allow asynchronous calls via multiple workers). The below steps assume that the `nginx` daemon is already set up on the remote machine instance, along with a system service to start/stop gunicorn.

### Update to the latest code version
`sudo` to the approved user `g-tracker` on the deployment server, and `git pull` the latest version of the code.
```sh
sudo -u g-tracker -i
cd WomenInMedia
git pull
```

### Restart the server
This step needs root access. To push dashboard and app updates to production, restart the `gunicorn` service as shown below.

To update the read dashboard, use the below command:
```sh
sudo service g-tracker restart
```

To update the read dashboard, use the below command:
```sh
sudo service g-tracker-admin restart
```

## Update `aliases.txt` file
The file `aliases.txt` exists to help deal with cases where different news outlets publish a person's name using a variety of aliases. For example, in quoting the British monarch Queen Elizabeth II, certain outlets might use the name "Queen Elizabeth", while others reference her official name "Queen Elizabeth II". Other situations where this occurs often include women and their maiden names, for example, "Sarah Huckabee Sanders". Certain organizations publish her name using just her post-marital name , "Sarah Sanders", while others refer to her combined birth/marital name, "Sarah Huckabee Sanders".

We address this naming inconsistency through an alias text file, that merges instances of aliases to a suitably chosen 'primary' name, i.e., the name we want to refer to the person by on our dashboard. The format of the alias file is as follows:

```
Primary name, alias1, alias 2, ...
Rahaf Mohammed al Qunun, Rahaf Mohammed Alqunun, Rahaf Mohammed
Queen Elizabeth II, Queen Elizabeth
Sarah Huckabee Sanders, Sarah Sanders
```

The first name in each line represents the primary name, and the remaining names (**separated by commas**) are the various aliases that different outlets use for that person. We can extend this list as much as required, and the corresponding dashboard app self-updates to aggregate the quote counts, merging instances of each alias to produce more accurate statistics.

#### Ensure Dash is serving custom JS locally
To ensure that Dash serves the JavaScript file from the local directory during deployment, ensure that the server config is set to `serve_locally` as shown below.

```python
app = dash.Dash(__name__, server=server, suppress_callback_exceptions=True)
app.css.config.serve_locally = True
app.scripts.config.serve_locally = True
```
Once these steps are followed, the server should begin tracking visits to the dashboard (it takes 1-2 days for stats to begin showing up on the Google Analytics account).


## Troubleshooting
Deployment of this application is slighly more contrived because of its multi-page structure. If the app does not deploy as expected, the error is likely related to relative paths and imports. First, make sure that all paths that reference files within the individual apps defined in `apps/` start from the root directory of the server (i.e. the directory in which `server.py` is defined).

Due to an [issue with circular imports](https://dash.plotly.com/urls) when defining multi-page applications in Plotly Dash, the Flask server object must be created in a separate file, which we call  `server.py`:

```python
server = flask.Flask(__name__)
server.secret_key = os.urandom(24)

app = dash.Dash(__name__, server=server, suppress_callback_exceptions=True)
app.css.config.serve_locally = True
app.scripts.config.serve_locally = True
```

As a result, this `server` object must be imported into `run.py` before deployment, so that it is available in the global scope for `gunicorn` to access.

```python
from server import app, server
```

Before deployment, ensure that the Flask server object defined in `server.py` is correctly defined and exposed to `gunicorn`, as per the below line in the `gunicorn` service:

```sh
ExecStart=/g-tracker/venv/bin/gunicorn --workers 3 --bind unix:g-tracker.sock -m 000 run:server
```

Here, `run:server` refers to the `server` object in `server.py`, run using `run.py`.

---

## Dashboard Design & Structure

This section describes the structure of the dashboard from a software design perspective. The primary design goals for using Plotly Dash and building this web app in Python are listed below:

* __Extensibility__: We want the system's layout to be flexible and open to adding new modules and apps in the future. To assist with this, we use a multi-page layout.
  
* __Modularity__: The system should properly divide unique functionality into separate files/modules, and contain the right levels of abstraction to allow new users to easily understand each app's structure.

* __Rapid iterability__: The system should be easy to build, deploy and test locally using minimal amounts of custom JavaScript/HTML/jQuery code. Writing most of the application's code in Python (with some CSS) has the benefit of reducing complexity, especially for new developers coming from a Data Science background, while improving the pace of testing incremental improvements and adding new functionality.
  
* __Responsiveness__: Each app's internal methods should ideally load and execute in near real-time - this is accomplished through the use of appropriate intermediate data structures stored in memory or using precomputed values from the database. If this is not possible, careful thought must be put into designing the right methods upstream to provide data to the app for a fluid runtime experience.

### Multi-page dashboard
The breakdown of this dash multi-page dashboard is shown below.

```
.
├── config.py
├── run.py
├── server.py
├── apps
|   ├── app1.py
|   ├── app2.py
|   └── app3.py
├── assets
|   ├── style.css
|   └── any_additional_styles.css
└── static
    ├── image1.png
    ├── image2.png
    └── logo.png
```
#### Root directory
This directory contains the main definition of the Flask server on top of which dash runs, as well as the index page (i.e. the entry point) to the dashboard, which contains the welcome information for the user to begin exploring content. For clarity, the default files shown in the Plotly Dash GitHub repo's [multi-page app example](https://github.com/plotly/dash-recipes/tree/master/multi-page-app) are renamed from (`index.py`, `app.py`) to (`run.py`, `server.py`) respectively.

The file `run.py` is the entry point to the dashboard and contains links to each of the individual apps in the dashboard. The file `server.py`, as described earlier, exists to separate the Flask server initialization from the callback definitions, which avoids issues with circular imports. `config.py` exists purely to store the different database settings and credentials that are used to read/write data in the applications.

#### Apps
Each application is stored as a separate Python file. Doing so allows each app's logic to be self-contained and it becomes very easy to add new, independent apps while linking them to the dashboard's entry point in `run.py`.

#### Assets
Keeping a distinct `style.css` file helps separate out the HTML element styling logic from the data and visualization logic in each app. Multiple CSS files can be added to this same directory to extend it further.

#### Static
This directory houses static files like logos or other files that are unrelated to the data flow within each app.

## Application code - readability guidelines
This section contains guidelines on making the application code containing unique functionality (such as "analyzing custom text", or "topic models") **more readable and maintainable** for future developers.

In general, a dash app should have three main sections, separated out by clearly labelled comment-blocks as shown below.

### 1. App layout
This code block is at the start of every app, immediately after module imports. The layout object is defined using dash's HTML wrappers, specified as a list of individual HTML objects written in Python. An example block is shown below.

```python
# Imports
import dash
import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Input, Output, State

# ========== App Layout ================
children_list = [
    html.Div(
        children=[
            html.H2('Analyzing gender balance'),
            html.Div(
                dcc.Textarea(
                    id='text-input',
                    placeholder='Enter your text to be analyzed'
                )
            )
            html.Div(
                [html.Button(id='submit', n_clicks=0, children='Submit')
            )
        ]
]

layout = html.Div(children=children_list)
```
Using this approach, an arbitrarily complex HTML layout can be specified, all in one place.

### 2. Callbacks
Callbacks are reactive, functional pieces of code that allow users to observe, modify and update properties of any component in the UI. In Dash, they are defined using Python's decorator syntax. A key aspect of callbacks are the fact that they track states *on button-clicks* as well as data, so it is recommended to make use of these functions wherever possible. An example callback is shown below.

```python
# ========== Callbacks ================
@app.callback([Output('input-1', 'data'), Output('input-2', 'data')],
              [Input('submit', 'n_clicks'), Input('reset', 'n_clicks')],
              [State('text-input', 'value')])
def update_output_div(submit_button, reset_button, input_text):
    """Return the male, female and unknown sources from the NLP function call"""
    ctx = dash.callback_context
    # Empty input text or reset button click returns nothing
    if not input_text or "reset" in ctx.triggered[0]["prop_id"]:
    # Define what an empty value should be represented by
        empty_value = {'female': [], 'male': [], 'unknown': []}
        return empty_values
    else:
        # Do something useful
        return something_useful
```

For better readability, it is strongly recommended to also define each chart/graph using a *separate* callback that is then referenced by ID in the app's layout. This is much preferable to defining the entire graph within the app layout itself (which can make the layout much harder to read and the code a lot uglier). An example of defining the graph as a callback and then calling it by ID into a given layout is shown below.

```python
# ========== App Layout ================
layout = html.Div([
    dcc.Graph(id='pie-chart-1')
], className='chart')

# ========== Callbacks ================
@app.callback(Output("pie-chart-1", "figure"), [Input('input-1', 'data')])
def update_pie(values):
    pie_dict = {
        'data': [{
            'type': 'pie',
            'values': values,
            'marker': {
                'colors': ['red', 'green', 'blue'],
                'line': {'color': 'white', 'width': 2}
            },
        }],
        'layout': {
            'title': "Percentage of females and males mentioned",
            'legend': {'orientation': 'v'},
        }
    }
    return pie_dict
```

Using this workflow, the app's *data logic* and its *design logic* are clearly separated. Additionally, the chart's sizing and alignment can be further customized using CSS, by specifying the `className` attribute.

### 3. Custom functions
In any reasonably complex app, there are bound to be a number of custom functions to perform data manipulation or other calculations. These can be defined in a third code section, separated by its own comment header as shown below. These functions can then be referenced directly in their respective callbacks.

```python
# ========== Callbacks ================
@app.callback(Output('source-display', 'children'), [Input('sources', 'data')])
def source_display_callback(store_data, case='sources'):
    return people_by_gender(store_data, 'sources')


# ========== Custom Functions ================
def format_names(case, name_list, gender):
    "Format output string from extracted sources/mentions"
    formatted = f"{case.title()} {gender}: {(', ').join(name_list)}" if name_list else ""
    return formatted


def people_by_gender(name_dict, case):
    """Return the person and source names for each gender as comma-separated strings"""
    female_names = format_names(case, name_dict['female'], 'female')
    male_names = format_names(case, name_dict['male'], 'male')
    unknown_names = format_names(case, name_dict['unknown'], 'unknown')
    # Format names with line break so we can render in Markdown
    formatted_names = '\n'.join([female_names, male_names, unknown_names])
    return formatted_names.strip()
```

Separating out code blocks into sections as shown above can greatly improve the readability of the code for future maintenance!

## Additional tips

### Limit the size of JSON objects being transferred
One of the caveats with storing all the data on MongoDB is that information must be passed around as JSON. Considering the size of data we have in GGT, **we only deal with aggregated quantities** in all the data we pass to Dash. This helps keep reasonable amounts of JSON data being passed through the network (which can be a bottleneck if it becomes really large). For our purposes in the GGT, because we want fast response times (and the fact that NLP operations are, in general, *very* expensive), we avoid working with moving around very large JSON blobs in each app's design.

### Sharing data between callbacks
On many occasions, we require a relatively expensive calculation (such as converting JSON data to a pandas DataFrame and manipulating the DataFrame's values) as a precursor to a Plotly chart. If the same calculation is being used to populate multiple charts, it makes sense to store the intermediate data obtained from the calculation rather than recomputing it for each callback.

Dash offers a `data` output type to handle this scenario. The `data` object is a JSON object that is stored in memory, and can be accessed any subsequent callback. This makes it very convenient to perform an expensive calculation just once, and passing parts of it to multiple callbacks down the line. An example is shown below.

Say we pull some JSON data from MongoDB and perform some expensive manipulation transformations on it, that then needs to be reused elsewhere. This can be done in a callback that outputs an intermediate "data" object as follows:

```python
@app.callback(Output('topic-data', 'data'), [Input('date-dropdown', 'value')])
def get_topic_data(value):
    with MongoClient(**MONGO_ARGS) as connection:
        read_collection = connection[READ_DB][READ_COL]
        data = read_collection.find({'_id': value})
        # Collect data
        data = list(data)[0]
        # Perform some expensive calculation
        data_transformed = expensive_calc(data)
    return data_transformed
```

Note the use of the `data` intermediate object in the callback's output. This intermediate JSON object can then be used (in part or in full) as input to any other callbacks as many times as required, without being computed again and again.

```python
@app.callback(Output('bar_plot', 'figure'), [Input('topic-data', 'data')])
def update_gender_bars(data):
    df = convert_json_to_pandas(data)  # Convert JSON data to a pandas DataFrame
    return = {
        'data' = [
            {
                'type': 'bar',
                'x': df['x'],
                'y': df['y']
            }
        ]
    }
```

For more details, see the Dash documentation on [sharing data between callbacks](https://dash.plotly.com/sharing-data-between-callbacks).
