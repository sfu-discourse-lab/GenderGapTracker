__Status: V7.0__ (Code provided as-is; only sporadic updates expected)

# Measuring gender bias in media

We present the code and framework for two bodies of work in this repo:

1. [The Gender Gap Tracker](https://gendergaptracker.informedopinions.org/) (GGT) for English news articles
2. [Radar de Parité](https://radardeparite.femmesexpertes.ca/) (RdP) for French news articles

The GGT and RdP are automated systems that measure men and women’s voices on mainstream Canadian news outlets in real time. We analyze articles from six English outlets (for the GGT) and six French outlets (for the RdP) in Canada using Natural Language Processing (NLP), and quantify the discrepancy in proportions of men and women quoted. Our larger goals through this project are to enhance awareness of women’s portrayal in public discourse through hard evidence, and to encourage news organizations to provide a more diverse set of voices in their reporting.

The Gender Gap Tracker is a collaboration between [Informed Opinions](https://informedopinions.org/), a non-profit dedicated to amplifying women’s voices in media and Simon Fraser University, through the [Discourse Processing Lab](https://www.sfu.ca/discourse-lab.html) and the [Big Data Initiative](https://www.sfu.ca/big-data/big-data-sfu).

## Publications
1. Asr FT, Mazraeh M, Lopes A, Gautam V, Gonzales J, Rao P, Taboada M. (2021) The Gender Gap Tracker: Using Natural Language Processing to measure gender bias in media. *PLoS ONE 16(1): e0245533*. https://doi.org/10.1371/journal.pone.0245533
2. Rao P, Taboada M. (2021), Gender bias in the news: A scalable topic modelling and visualization framework. *Frontiers in Artificial Intelligence, 4(82)*. https://doi.org/10.3389/frai.2021.664737
3. Soumah, V.-G., Rao, P., Eibl, P., & Taboada, M. (2023). Radar de Parité: An NLP system to measure gender representation in French news stories. *Proceedings of the Canadian Conference on Artificial Intelligence*. https://doi.org/10.21428/594757db.b6f3c89e


## Contributors

See [CONTRIBUTORS.md](CONTRIBUTORS.md)
## Contents of this repo

* `scraper`: Modules for scraping English and French news articles from various Canadian news organizations' websites and RSS feeds.
* `nlp`: NLP modules for performing quote extraction and entity gender annotation on both English and French news articles.
* `api`: FastAPI code base exposing endpoints that serve our daily statistics to public-facing dashboards: [Gender Gap Tracker](https://gendergaptracker.informedopinions.org) and [Radar de Parité](https://radardeparite.femmesexpertes.ca)
* `research_dashboard`: [A multi-page, extensible dashboard](https://gendergaptracker.research.sfu.ca/) built in Plotly Dash that allows us to explore the GGT data in more detail.
* `statistics`: Scripts for running batch queries on our MongoDB database to retrieve source/gender statistics.

## Data

Both the English and French datasets were downloaded from public and subscription websites of newspapers, under the ‘fair dealing’ provision in Canada’s Copyright Act. This means that the data can be made available (upon signing a licence agreement) **only** for non-commercial and/or research purposes.

## Future directions

In future versions of the software, we are planning to visualize more fine-grained information about who is being quoted, separating politicians, witnesses and/or victims, from experts (as informed sources of analysis, context and opinion). We are also looking into different ways of separating wire copy from the original publication of each news outlet in order to provide a clearer view of the gender gap in Canadian media, produced by the news outlets themselves.

From a research perspective, questions of salience and space arise, i.e., whether quotes by men are presented more prominently in an article, and whether men are given more space in average (perhaps counted in number of words). More nuanced questions that involve language analysis include whether the quotes are presented differently in terms of endorsement or distance from the content of the quote (*stated* vs. *claimed*). Analyses of transitivity structure in clauses can yield further insights about the type of roles women are portrayed in, complementing some of our studies' findings via dependency analyses.

We are mindful of and acknowledge the relative lack of work in NLP in languages other than English. We believe that we have played at least a small role here, through our analyses in the Radar de Parité on French news articles, though there still remains a lot more to be done in this domain. Our hope is that further such work will yield not only interesting methodological insights, but also reveal larger similarities in gender disparities in other regions of the world. While we are actively pursuing such additional areas of inquiry, we also invite other researchers to join in this effort!


## Contact

For more information about the research methodology and for questions regarding collaboration, please contact Dr. Maite Taboada.

> **Maite Taboada**  
mtaboada@sfu.ca  
Director, Discourse Processing Lab  
Simon Fraser University  
Burnaby, British Columbia, Canada  
