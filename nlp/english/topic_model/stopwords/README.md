# Stopwords for Topic Modelling
Choosing the right stopwords for topic modelling is an iterative process [[1]](https://databricks.com/blog/2015/09/22/large-scale-topic-modeling-improvements-to-lda-on-apache-spark.html). Based on the news outlet vocabulary in our corpus, certain common verbs can hinder the interpretation of topics. Most nouns, however, are useful for interpreting topics as they offer some context to the news categories being covered.

The below lists of words are combined to produce the overall stopword list used in topic modelling.

## NLTK (curated)
From past projects at the discourse processing lab, the default NLTK stopword list was curated and some additional common charactes/symbols/digits added to this list. This list of words is in the file `nltk_curated.txt`.

## Light verbs
These are [verbs with little semantic content of their own](https://en.wikipedia.org/wiki/Light_verb), such as *do, give, make, take*. The list of light verbs relevant to the GGT news corpus is extended and customized (with some trial and error based on intermediate topic model results) and added to the file `create_stopword_list.py`.

**NOTE**: In the Python file, just the verb roots are specified manually. The full list of verbs (in present/past tenses) is obtained by looking up each lemma's alternate forms from spaCy's lemma dictionary.

## Custom words
Initially, an additional list of "general" nouns, or [signalling nouns](https://books.google.ca/books/about/Signalling_Nouns_in_Academic_English.html?id=3f-XoAEACAAJ&redir_esc=y), or [shell nouns](https://www.aclweb.org/anthology/W13-2314/) was considered. These include certain abstract nouns like "problem", "fact" or "result" - i.e. nouns with non-specific meaning when considered in isolation. It was found that most of these nouns are actually very useful in interpreting topics, which in itself is a task where words (especially nouns) are looked at in isolation.

As a result, general/signalling/shell nouns are **not** used in this task.

However, based on the initial topic modelling experiments run, a separate list of custom words that hinder topic interpretability were created manually. The below words were included in the file `create_stopword_list.py`.

* **Social media-related**: *post, sign, like, love, tag, star, call, group, video, photo, pic, inbox*
* **URL and embed terms**: *http, https, href, ref, com, cbc, ctv, src, twsrc, 5etfw*
* **Frequently occurring common nouns**: *people, man, woman, life, family, friend, news, report, press, page, story*
* **Time of the day/week**: *morning, afternoon, evening, today, yesterday, tomorrow*
* **Time periods**: *day, week, month, year*
* **Time zones**: *edt, pst*
* **Day of the week**: *monday, tuesday, wednesday, thursday, friday, saturday, sunday*
* **Months of the year**: *january, february, march, ..., october, november, december*
* **Year**: *2018, 2019, 2020, 2021*

## Generate a final list of stopwords
The included Python file is run as follows.
```
python3 create_stopword_list.py
```

This concatenates words from the above lists into a single, de-duplicated set and sorts them in alphabetical order, producing a final stopword file `stopwords.txt`.

## References
[1] [Large Scale Topic Modeling: Improvements to LDA on Apache Spark](https://databricks.com/blog/2015/09/22/large-scale-topic-modeling-improvements-to-lda-on-apache-spark.html)