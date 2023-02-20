# Radar de Parité: API

FastAPI code base for the API that serves the [Radar de Parité public dashboard](https://radardeparite.femmesexpertes.ca/). The dashboard itself is hosted externally, and its front end code is hosted on this [GitLab repo](https://gitlab.com/client-transfer-group/rdp).

## API docs

The docs can be accessed in one of two ways:

* Swagger: https://radardeparite.femmesexpertes.ca/docs
  * Useful to test out the API interactively on the browser
* Redoc: https://radardeparite.femmesexpertes.ca/redoc
  * Clean, modern UI to see the API structure in a responsive format

## Extensibility

The code base has been written with the intention that future developers can add endpoints for other functionality that can potentially serve other dashboards.

* `db`: Contains MongoDB-specific code (config and queries) that help interact with the RdP data on our MongoDB database
* `endpoints`: Add new functionality to process and serve results via RESTful API endpoints
* `schemas`: Perform response data validation so that the JSON results from the endpoint are formatted properly in the docs
* `utils`: Add utility functions that support data manipulation within the routers
* `gunicorn_conf.py`: Contains deployment-specific instructions for the web server, explained below.

## Deployment

We perform a standard deployment of FastAPI in production, as per the best practices [shown in this blog post](https://www.vultr.com/docs/how-to-deploy-fastapi-applications-with-gunicorn-and-nginx-on-ubuntu-20-04/).

* `uvicorn` is used as an async web server (compatible with the `gunicorn` web server for production apps)
* `gunicorn` works as a process manager that starts multiple `uvicorn` processes via the `uvicorn.workers.UvicornWorker` class
* `nginx` is used as a reverse proxy

The deployment and maintenance of the web server is carried out by SFU's Research Computing Group (RCG).


