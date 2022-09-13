# Corpus analysis of topic model results

This directory contains scripts to help with digging deeper into the GGT topic model results. In the current topic model production pipeline that runs monthly on the `rcg-ggt-topic.dcr.sfu.ca` instance, we write out CSV files containing the IDs, URLs and the source counts (for male and female sources) for each article along with the article's topic distribution to the **`WomenInMedia/NLP/topic_Model/topic_split_csv`** directory. A simplified example is shown below for illustration purposes.

| _id | sourcesMaleCount | sourcesFemaleCount | url | t1 | t2 | ... | t15 |
| --- | ---: | ---: | --- | ---: | ---: | --- | ---: |
| 1 | 3 | 0 | ...| 0.003 | 0.099 | ... | 0.0001 |
| 2 | 1 | 3 | ...| 0.001 | 0.097 | ... | 0.0006 |
| 3 | 4 | 1 | ...| 0.004 | 0.096 | ... | 0.0002 |
| 4 | 0 | 2 | ...| 0.008 | 0.095 | ... | 0.0007 |

In essence, each article ID stores the number of sources by gender, as well as the topic weight distribution from `t1` to `t15` as shown. A high value topic weight for a particular topic (e.g. `t2` in this case) means that the article's vocabulary strongly focuses on the keywords for that topic.

## Methodology
The below methodology is used to perform corpus analysis on the topic model results for a particular month.

### Identify a topic of interest
As a first step, we can look at the [topic model dashboard](https://gendergaptracker.research.sfu.ca/apps/topicmodel) to see which topics are interesting for a particular month. An "interesting" topic here is one that shows trends that we would like to explore further, for example, identifying why a topic (e.g. 'Business & market events') showed stronger male prominence than female.

### Look at the admin dashboard to match the topic name with its number
Because the CSV files only store topic numbers (`t1`, `t2`, etc.), we need to look at the [admin dashboard](https://admin.gendergaptracker.research.sfu.ca/) to match the topic *label* ('Business & market events') to its *number* for a given month (e.g. `t2`). Once we know what number represents a topic of interest, we can proceed to the next step.

### Sort the CSV file based on the topic number
Now that we identified topic `t2` as the topic of interest for a given month, we sort the article IDs for this month in descending order of the value of topic weight for topic `t2`, as shown in the example table. This way, we capture the "top" articles that are strongly related to topic `t2`.

### Separate the article IDs into two sets based on gender of sources
Next, we split the CSV results into two sets - one that contains only IDs in which more men were quoted than women, and vice versa. We call these "male-dominated" and "female-dominated" article lists. This is done so that we can perform a deeper analysis on each set of articles' text based on which gender is more quoted.

### Download article full-body test from the database
We use the article IDs for each set (male-dominated and female-dominated sources) to query the database, and output the full article content for each ID to a separate text file. To keep the number of articles reasonable, **we limit the articles downloaded to 200 for each gender**. Based on an inspection of the typical topic strengths for a number of topics over many months, it was clear that topic weights for a particular topic (e.g. `t2`) quickly dropped to below 0.6 after around 400-500 articles (once they were sorted in descending order of topic weights). This means that our rule of extracting 200 articles for male/female-dominated articles is reasonable for the vast majority of topics considered.

### Pass the article body text to `corpus_toolkit` for corpus analysis
We use the [`corpus_toolkit`](https://github.com/kristopherkyle/corpus_toolkit) library, written by Kristopher Kyle. This is a corpus analysis library built on top of spaCy, and is very effective in quickly analyzing and comparing two corpora using a variety of techniques from corpus linguistics. A full overview of corpus linguistics is out of the scope of this README, so it is recommended to look at [the documentation](https://github.com/kristopherkyle/corpus_toolkit) of the `corpus_toolkit` library on GitHub. 

For our topic model analysis, we use two methods from corpus linguistics:
* Keyness
* Dependency bigrams

---

## Background on Keyness
Keyness analysis helps understand the difference between two corpora by comparing the relative frequencies of terms that occur in them, and highlighting the differences that are statistically significant. A detailed history of keyness and the metrics it uses is provided by [Gabrielatos, C. “Chapter 12 : Keyness Analysis : nature , metrics and techniques.” (2017)](https://core.ac.uk/download/pdf/227092349.pdf).

The keyness analysis function in `corpus_toolkit` returns the "log-ratio" metric, output in the form of a keyness index that varies from positive (for terms in the female-dominated corpus) to negative (for terms in the male-dominated corpus). A more detailed description of the log-ratio metric and why it is relevant for keyness is provided by [Hardie (2014)](http://cass.lancs.ac.uk/log-ratio-an-informal-introduction/).

## Background on dependency bigrams
Corpus linguistics offers a range of techniques to study the occurrences of specific parts of speech (`NOUN`, `ADJ`, `VERB`) as well as n-grams (bigrams or trigrams) or collocation of terms based on a user-provided keyword. From our experiments for the topic model analysis, these methods did not generally reveal anything fundamentally new about the content in each corpus. However, studying **dependency bigrams** did seem to help in understanding the connection between subjects/objects and the actions they take, so we make use of this method in the corpus analysis.

To calculate dependency bigrams, spaCy’s dependency parser is used to identify pairs of words, i.e. bigrams that are syntactically connected by a head-dependent relationship (See the [`corpus_toolkit` documentation](https://github.com/kristopherkyle/corpus_toolkit)). An example is shown below.

>  In the clause "The player *kicked* the **ball**", the main verb *kicked* is connected to the **noun** ball via a direct object relationship, wherein *kicked* is the head and **ball** is the dependent.”

Extracting dependency bigrams from the above example should return the result `ball_kick`. As can be seen, this helps study the connection between subjects/objects and the actions they take, which is useful in  and analyzing topic model results.

---

## Installation
Install the required modules from `requirements.txt` as follows. We also need to download and install the spaCy small language model for `corpus_toolkit`.

```sh
python3 -m venv venv
source venv/bin/activate 
pip3 install -r requirements.txt
python3 -m spacy download en_core_web_sm
```

For further development, simply activate the environment as follows:
```sh
source venv/bin/activate
```

### Run article download script
First, download the CSV files for a particular month from the topic model VM are downloaded (from `/data/WomenInMedia/NLP/topic_model/topic_split_csv`) and place them into a local directory called `csv`.

For a particular topic of interest for a particular month's data (say `t2`), download the top 200 articles for that month as follows.

```sh
python3 download_articles.py -f csv/topicSplit_2020-07.csv -t t2 --limit 200
```
The `--limit` argument allows use to limit the download to any number of articles, in this case 200.

Running this script downloads the top `n` article's raw body text (as specified by the `--limit` argument) and places them in two separate directories, depending on which gender was more quoted in each article.

From the above example command, we obtain a directory structure as follows:
```
.
├── analyze.py
└── topicSplit_2020-07
    └── t2
        └── male
        └── female
```
Each of the directories `male` and `female` contain 200 text files with the article bodies' text for the given topic (`t2`).

### Analyze keyness and dependency bigrams
To run keyness and extract dependency bigrams, as well as plot them for easy interpretation, use the `analyze.py` script. For the same example topic `t2`, an example command is given below.

```sh
python3 analyze.py -f topicSplit_2020-07 -t t2
```
This command runs through the 200 articles in each of the male/female directories for that topic, and outputs a directory `Plots` with lollipop plots showing the top keywords from the keyness analysis. By default, **only** the keyness analysis is run in this script.

To extract dependency bigrams and plot them, include the `--dep_bigrams` booleab argument.

```sh
python3 analyze.py -f topicSplit_2020-07 -t t2 --dep_bigrams
```
This outputs the dependency bigrams ranked by frequency of occurrence in either corpus (male/female) alongside the keyness results. 

### (Optional): Experiment with other corpus analysis techniques
To test out other techniques from corpus linguistics, use the `test_corpus_functions.py` script. This contains additional methods to compare two corpora's top words based on their part-of-speech tags (e.g. `NOUN`, `ADJ` or `VERB`). In addition, it contains a means to study the collocates (words that regularly appear in the vicinity) of a particular word specified by the user. These methods can be turned on and off by commenting the respective liens in the `main()` function.

```sh
python3 test_corpus_functions.py -f topicSplit_2020-07 -t t2
```
Because this script is primarily for experimentation purposes, it doesn't output any plots - the results are just printed to the console.

Initial experiments with POS-tags and the collocation didn't show results that revealed any new insights - so these functions were left out of the main analysis script. However, a deeper analysis of these methods might yield something useful, so the test script is included here for future reference.