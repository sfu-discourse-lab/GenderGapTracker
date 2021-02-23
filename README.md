__Status: V5.3__ (Code provided as-is; only sporadic updates expected).

# The Gender Gap Tracker

This repo contains the code and framework used in our study on gender bias in the media. We present the [Gender Gap Tracker (GGT)](https://gendergaptracker.informedopinions.org/), an automated system that measures men and women’s voices on
seven major Canadian news outlets in real time. We analyze the rich information in news articles using Natural Language Processing (NLP) and quantify the discrepancy in proportions of men and women quoted. Our larger goals through this project are
to enhance awareness of women’s portrayal in public discourse through hard evidence, and to  encourage news organizations to provide a more diverse set of voices in their reporting.

The Gender Gap Tracker is a collaboration between [Informed Opinions](https://informedopinions.org/), a non-profit dedicated to amplifying women’s voices in media and Simon Fraser University, through the [Discourse Processing Lab](https://www.sfu.ca/discourse-lab.html) and the [Big Data Initiative](https://www.sfu.ca/big-data/big-data-sfu).

## Research Paper
> Asr FT, Mazraeh M, Lopes A, Gautam V, Gonzales J, Rao P, Taboada M. (2021) The Gender Gap Tracker: Using Natural Language Processing to measure gender bias in media. PLoS ONE 16(1): e0245533. https://doi.org/10.1371/journal.pone.0245533

## Contributors

See [CONTRIBUTORS.md](CONTRIBUTORS.md)

## Contents of this repo

* `dashboard_for_research`: [Research dashboard and apps](https://gendergaptracker.research.sfu.ca/) that allow us to explore the GGT data in more detail.
* `NLP`: NLP modules for performing quote extraction and entity gender annotation on the news articles.
* `scraping_and_aggregation`: Modules for scraping news articles from various Canadian news organizations' websites, and the code we use to extract aggregate statistics from the database.

## Future directions

Future research directions include an examination of how female and male quotations are distributed in the articles from different topics and written by female vs. male authors. In future versions of the software, we are planning to visualize more fine-grained information about who is being quoted, separating politicians, witnesses and/or victims, from experts (as informed sources of analysis, context and opinion). Finally, we are looking into different ways of separating wire copy from the original publication of each news outlet in order to provide a clearer view of the gender gap in Canadian media, produced by the news outlets themselves. 

## Data

The data was downloaded from public and subscription websites of newspapers, under the ‘fair dealing’ provision in Canada’s Copyright Act. This means that the data can be made available (upon signing a licence agreement) **only** for non-commercial and/or research purposes.

## Contact

For more information about the research methodology and for questions regarding collaboration, please contact:

__Maite Taboada__  
mtaboada@sfu.ca  
Director, Discourse Processing Lab  
Simon Fraser University

