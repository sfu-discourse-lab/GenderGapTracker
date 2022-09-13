# Lemmatization workflow
We lemmatize all terms in each document prior to topic modelling in Spark. In our initial experiments, we observed that the lemmatizer used by Spark NLP (the third party used for lemmatization in Spark) was not of the requisite quality for our purposes. As a result, we chose to use spaCy's [lemma lookup data available on GitHub](https://github.com/explosion/spacy-lookups-data/tree/master/spacy_lookups_data/data).

## Formatting
The lemmas from spaCy's lookup data are available as JSON, specified as `{lemma: [word1, word2, ...]}` where each key is the lemma, and the value is a list of words that share that lemma . In addition, a lot of the lemma keys contain extraneous symbols and punctuation, which we know are cleaned in an upstream step in our topic modelling pipeline. As a result, we don't need to include such entries with symbols and punctuation, because they will never be looked up in our topic model pipeline. 

Spark NLP expects lemmas to be in the following format -- note that it uses space-separated words in a flat file format (no JSON).

```
colony -> colony colonies
colonisation -> colonisation colonisations
colonise -> colonise colonised colonises colonising
coloniser -> coloniser colonisers
colonist -> colonist colonists
colonization -> colonization colonizations
colonize -> colonize colonized colonizes colonizing
colonizer -> colonizer colonizers
```

When we load in the lemma lookup table as shown above to Spark, we can specify the separator symbol (`-->`), that indicates to Spark that the lemma is on the left and the words that share that lemma are on the right of that separator.

## Preparing the lemma lookup file
In our experiments over many months' of real world data, we observed certain words like "data", which occur very regularly in the news, were reduced to "datum" during lemmatization. This is not ideal during topic keyword interpretation for labelling the topics. As a result, we define a "ban list" of lemmas in the file `convert_spacy_lemmas.py`, currently consisting of just the lemma "datum". In specifying this list, we are able to exclude it from the generated lookup file for Spark, so that when the model encounters words like "data", it does not reduce it to its lemma form (it is kept as "data").

The order of steps in generating an up-to-date lemma lookup table for Spark via spaCy is below.

1. In `convert_spacy_lemmas.py` define a ban list of lemmas that shouldn't be considered during lemmatization. Words that have this as a lemma in spaCy's English lemma lookup are not lemmatized as a result.
2. Run the rile `convert_spacy_lemmas.py` (one-time process each time we want to update the lemma list) -- this downloads the latest English lemma lookup JSON from spaCy's GitHub repo, formats it and removes the unnecessary lemmas as we defined in the script.
3. Commit both `convert_spacy_lemmas.py` as well as generated text file `spacy_english_lemmas.txt` to GitHub. Pull the latest code on the topic modelling VM to ensure that the latest lemma list is in use for our monthly pipeline.