# Gender Gap Tracker: API

This section contains the code for the API that serves the [Gender Gap Tracker public dashboard](https://gendergaptracker.informedopinions.org/). The dashboard itself is hosted externally, and its front end code is hosted on this [GitLab repo](https://gitlab.com/client-transfer-group/gender-gap-tracker).

## API docs

The docs can be accessed in one of two ways:

* Swagger: https://gendergaptracker.informedopinions.org/docs
  * Useful to test out the API interactively on the browser
* Redoc: https://gendergaptracker.informedopinions.org/redoc
  * Clean, modern UI to see the API structure in a responsive format


## Run tests

Tests are run via `pytest`. Set up an ssh tunnel on a Unix shell to forward the MongoDB host connection to the local machine on port 27017 as follows. In the example below, `vm12` is the alias for the primary node of the MongoDB cluster.

```
$ ssh vm12 -f -N -L 27017:localhost:27017
```
Run the tests:

```sh
$ cd /path_to_repo/api/english
$ python -m pytest -v
```

## Extensibility

The code base has been written with the intention that future developers can add endpoints for other functionality that can potentially serve other dashboards.

* `db`: Contains MongoDB-specific code (config and queries) that help interact with the RdP data on our MongoDB database
* `endpoints`: Add new functionality to process and serve results via RESTful API endpoints
* `schemas`: Perform response data validation so that the JSON results from the endpoint are formatted properly in the docs
* `utils`: Add utility functions that support data manipulation within the routers
* `tests`: Add tests to check that data from the endpoints are as expected for the front end
* `gunicorn_conf.py`: Contains deployment-specific instructions for the web server, explained below.

## Deployment

We perform a standard deployment of FastAPI in production, as per the best practices [shown in this blog post](https://www.vultr.com/docs/how-to-deploy-fastapi-applications-with-gunicorn-and-nginx-on-ubuntu-20-04/).

* `uvicorn` is used as an async web server (compatible with the `gunicorn` web server for production apps)
  * We set `uvicorn` to use `uvloop` instead of `asyncio` to handle async coroutines under the hood (due to a bug with `asyncio` on CentOS)
* `gunicorn` works as a process manager that starts multiple `uvicorn` processes via the `uvicorn.workers.UvicornWorker` class
* `nginx` is used as a reverse proxy

The deployment and maintenance of the web server is carried out by SFU's Research Computing Group (RCG).



