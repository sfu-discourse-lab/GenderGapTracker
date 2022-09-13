# Custom rules and word lists for NLP module

- [Custom rules and word lists for NLP module](#custom-rules-and-word-lists-for-nlp-module)
  - [Author name rules](#author-name-rules)
    - [1. Author Blocklist](#1-author-blocklist)
    - [2. Human-curated name pattern list](#2-human-curated-name-pattern-list)
  - [Quoting verbs](#quoting-verbs)
    - [Which verbs were removed from the MDS students' list?](#which-verbs-were-removed-from-the-mds-students-list)
    - [Final quote verb allow-list](#final-quote-verb-allow-list)

This directory contains any custom rules or lists that are used to enhance the results of the NLP module.

## Author name rules

During scraping, author names are automatically extracted from the article byline. Due to inconsistencies in the way different outlets store their author name fields, the scraper returns a number of useless extra fields, such as web URL artifacts or publishing house names - these must be dealt with before passing the list to the author gender annotator, otherwise we risk assigning a gender to non-human entities.

To do this, a two-step process is applied during author name cleaning.

### 1. Author Blocklist
A blocklist (`blocklist_authors.txt`) is defined to remove author names if they contain any words from the blocklist. The reasoning is that a pure-author name (i.e. a person) would be mentioned inside a separate set of HTML tags, so any "names" that contain blocklist words must have been incorrectly scraped. The author blocklist words come from the following broad family of words.

* __Publishing houses__: *Cbc, ctv, Canadian, Presse, Agence, Afp, Reuters,Thestar, Starmetro, Washington, Times, Tribune ...*
* __Local outlets and offices__: *Vancouver, Calgary, Halifax, Ottawa ...*
* __URL artifacts__: *Http, Https, Www,Facebook.com, Getty, Images, Twitter, Gmail, Mail,...* 
* __Timezones and time periods__: *Am, Pm, Edt, Edtlast, Day Ago, Last, Updated ...*

### 2. Human-curated name pattern list
Named Entity Recognition (NER) is done using the spaCy library. For author names that slip through the cracks during blocklist lookup, we run NER on the remaining fields to further filter them down to just person names. Even the largest (`en_core_web_lg`) spaCy language model will miss some perfectly valid person names.

To help with this issue, a human-evaluation of a large list of existing author names from the database was done for a separate task (newswire article identification). The names extracted from this task are stored on Vault:
*GRIM/general/Newswire_project/Author_attribution_sample_w_affiliations_completed.xlsx*.

This file contains the names of more than 800 authors from various outlets. A simple script is run to identify which of these names are *not* detected by spaCy's large language model.

```python
import pandas as pd
import spacy


def get_namesDF(filepath):
    names = []
    with open(filepath) as f:
        for line in f:
            names.append(line.strip())
    namesDF = pd.DataFrame.from_dict({'names': names})
    return namesDF


def check_names(name):
    persons = set()
    with nlp.disable_pipes("tagger", "parser"):
        doc = nlp(name)
        for ent in doc.ents:
            if ent.label_ == 'PERSON' and len(ent) > 1:
                persons.add(ent)
    return list(persons)


if __name__ == "__main__":
    nlp = spacy.load('en_core_web_lg')

    names_file = 'person_names.txt'
    namesDF = get_namesDF(names_file)
    namesDF['namesPerson'] = namesDF['names'].apply(check_names)
    namesDF.to_csv('person_names.csv', index=False)
```

Fields that are blank in the `namesPerson` column are missed by spaCy. Other names could be mis-identified as `PERSON` when in fact they are of the type `GPE` (geo-political entity) or `ORG` (organization). Such named entity patterns are stored as spaCy NER rules in the `name_patterns.jsonl` file, a snippet of which is shown below.

```json
{"label": "GPE", "pattern": "Niagara Falls"}
{"label": "ORG", "pattern": "OC Transpo"}
{"label": "PERSON", "pattern": "Penny Smoke"}
{"label": "PERSON", "pattern": "Hope Yen"}
{"label": "PERSON", "pattern": "Terray Sylvester"}
{"label": "PERSON", "pattern": "Morgan Black"}
{"label": "PERSON", "pattern": "Jordan Press"}
{"label": "PERSON", "pattern": "Morgan Campbell"}
{"label": "PERSON", "pattern": "Farai Mutsaka"}
{"label": "PERSON", "pattern": "Patience Haggin"}
```

The rules are parsed prior to loading the language model in the entity gender annotator and added as a downstream component of the spaCy NLP pipeline with the `overwrite_ents=True` flag enabled - this forces exact-matches of the patterns to be assigned the type `PERSON`. 

```python
    nlp = spacy.load('en_core_web_lg')
    ruler = EntityRuler(nlp, overwrite_ents=True).from_disk(NER_PATTERNS)
    nlp.add_pipe(ruler)
```

---

## Quoting verbs

For V5 of the quote extractor, an extended list of quote verbs allowed was obtained through our collaboration with UBC MDS students as part of their Capstone project. To begin, the students used [the Penn Attribution Relations Corpus (PARC 3.0)](https://www.aclweb.org/anthology/L16-1619.pdf), an annotated quote attribution dataset that provides over 16,000 quotes along with their speaker and quoting verbs. Of these articles, a subset are from the news domain, so only these were chosen to help us identify more quoting verbs used in the news. 

GloVe word embeddings were used to represent the quoting verbs used in the existing V4 verb list as well as the PARC 3.0 dataset. It is known that words that are semantically related with one another in the embedding space tend to cluster together, so a larger list of verbs that had a cosine similarity of > 50% with the existing verbs were extracted from the embedding space. From this extensive list of verbs, some hand-filtering was performed to reduce the verbs to those commonly seen as quoting verbs in news articles.

On our end at the discourse lab, we went through a further trial and error process to fine-tune the MDS students' quote verb list by testing article snippets on our [Text Analyzer dashboard](https://gendergaptracker.research.sfu.ca). The below list is a lemmatized version of that generated by the MDS students in the Capstone project.

```
[
    'accept', 'acclaim', 'acknowledge', 'add', 'address', 'admit', 'advise',
    'announce','argue', 'assert', 'assure', 'believe', 'claim', 'clarify',
    'comment', 'conclude', 'confirm', 'continue', 'convince', 'criticize',
    'declaim', 'declare', 'decry', 'demonstrate', 'denounce', 'describe',
    'disclaim', 'dispute', 'ensure', 'estimate', 'exclaim', 'explain',
    'find', 'highlight', 'illustrate', 'indicate', 'inform', 'insist',
    'mention', 'note', 'notify', 'persist', 'point', 'preach', 'predict',
    'present', 'proclaim', 'provide', 'rave', 'reassert', 'reassure',
    'reckon', 'reconfirm', 'release', 'remind', 'reply', 'report',
    'respond', 'restate', 'retell', 'say', 'speak', 'state', 'suggest',
    'tell', 'think', 'testify', 'tweet', 'warn', 'write'
]
```

### Which verbs were removed from the MDS students' list?
Based on our internal discussions, we found through extensive Google searches of online articles that verbs such as "address", "believe" and "provide" (originally included by the MDS students) were not very useful in capturing quotes. They tended to produce false positives, and in many cases, failed to match quotes altogether in our tests. As a result, **these verbs are removed** from our final list.

The words "ensure" and "continue" were also extensively tested on the dashboard, and it was found through Google searches that these are commonly used quote verbs in Canadian news articles.

> Ontario Premier Doug Ford didn't reference the death during his remarks Tuesday, but he did underscore the danger that the coronavirus poses. COVID-19 constitutes a danger of major proportions," he **continued**. "We must act decisively. We must not delay."

> Prime Minister Justin Trudeau confirmed that the cause of the crash is still entirely unknown, but he **ensured** Canadians that it will be thoroughly investigated as soon as possible.

The remaining verbs in the MDS students' list were kept because they were seen to be quite regularly used as quoting verbs in the news.


### Final quote verb allow-list
The finalized list of verbs are converted to all their forms (present/past tense) and stored in the file `quote_verb_list.txt`. This allow-list is used during quote extraction by the syntactic quote extraction function.
