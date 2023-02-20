# APIs for public-facing dashboards

This section hosts code for the backend APIs that serve our public-facing dashboards for our partner organization, Informed Opinions.

We have two APIs: one each serving the English and French dashboards (for the Gender Gap Tracker and the Radar de Parité, respectively).

## Dashboards
* English: https://gendergaptracker.informedopinions.org
* French: https://radardeparite.femmesexpertes.ca

### Front end code

The front end code base, for clearer separation of roles and responsibilities, is hosted elsewhere in private repos. Access to these repos is restricted, so please reach out to mtaboada@sfu.ca to get access to the code, if required.

## Setup

Both APIs are written using [FastAPI](https://fastapi.tiangolo.com/), a high-performance web framework for building APIs in Python.

This code base has been tested in Python 3.9, but there shouldn't be too many problems if using a higher Python version.

Install the required dependencies via `requirements.txt` as follows.

Install a new virtual environment if it does not already exist:
```sh
$ python3.9 -m venv api_venv
$ python3.9 -m pip install -r requirements.txt
```

For further use, activate the virtual environment:

```sh
$ source api_venv/bin/activate
```


