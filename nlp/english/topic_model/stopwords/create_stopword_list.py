"""
Script to generate a custom list of stopwords that extend upon existing word lists.
"""
import json
from urllib.request import urlopen
from itertools import chain


def combine(*lists):
    "Combine an arbitrary number of lists into a single list"
    return list(chain(*lists))


def get_spacy_lemmas():
    "Read in spaCy lemma dict from the raw GitHub source"
    spacy_lemma_url = "https://raw.githubusercontent.com/explosion/spacy-lookups-data/master/spacy_lookups_data/data/en_lemma_lookup.json"
    with urlopen(spacy_lemma_url) as response:
        lemmas = response.read()
    return json.loads(lemmas)


def get_words(filename):
    "Read in a list of words from a stopword list"
    words = []
    with open(filename) as f:
        for word in f:
            words.append(word.strip())
    return words


def lookup_verbs(roots, spacy_lemmas):
    """Return a full of list light verbs and all its forms (present, past tense, etc.)"""

    def flatten(list_of_lists):
        "Return a flattened list of a list of lists"
        return [item for sublist in list_of_lists for item in sublist]

    verblist = []
    for root in roots:
        verbs = [key for key in spacy_lemmas if spacy_lemmas[key] == root]
        verbs.append(root)
        verblist.append(verbs)
    return flatten(verblist)


if __name__ == "__main__":
    # We first get the NLTK curated word list
    nltk_stopwords = set(get_words('nltk_curated.txt'))
    # Obtain spaCy lemma dictionary for retrieving light verb full forms 
    spacy_lemmas = get_spacy_lemmas()

    # Create custom word lists depending on the class of words seen in the data
    url_terms = ['href', 'http', 'https', 'src', 'twsrc', '5etfw', 'ref', 'com', 'cbc',
                 'ctv', 'star', '5127en', 'httpstco', 'www']
    # Don't take 'wed', 'sat' and 'sun' because they are also normal words
    days_of_the_week = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday',
                        'saturday', 'sunday', 'mon', 'tue', 'thu', 'fri']                    
    months_of_the_year = ['january', 'february', 'march', 'april', 'may', 'june', 'july',
                          'august', 'september', 'october', 'november', 'december', 'jan',
                          'feb', 'mar', 'apr', 'jun', 'jul', 'aug', 'sep', 'sept', 'oct',
                          'nov', 'dec']
    years = ["2018", "2019", "2020", "2021", "2022", "2023"]
    time_periods = ['minute', 'minutes', 'hour', 'hours', 'day', 'days', 'week', 'weeks',
                    'month', 'months', 'year', 'years']
    time_related = ['yesterday', 'today', 'tomorrow', 'day', 'night', 'morning',
                    'afternoon', 'evening', 'edt', 'est', 'pst', 'pdt', 'time', 'times']
    common_words = ['press', 'news', 'report', 'page', 'user', 'reuters', 'email', 'browser',
                    'file', 'files', 'video', 'pic', 'photo', 'online', 'social', 'media', 'article',
                    'group', 'inbox', 'item', 'advertisement', 'world', 'store', 'story',
                    'life', 'family', 'people', 'man', 'woman', 'friend', 'friends']
    social_media = ['twitter', 'facebook', 'google', 'gmail', 'linkedin', 'pinterest', 'getty',
                    'video', 'photo', 'image', 'images', 'user', 'social', 'media', 'newsletter',
                    'subscribe', 'page', 'online', 'live', 'stream', 'post', 'app', 'postmedia',
                    'apnews']
    light_verb_roots = ['call', 'click', 'continue', 'comment', 'do', 'feel', 'find',
                        'give', 'get', 'have', 'include', 'like', 'live', 'love', 'make',
                        'post', 'read', 'say', 'speak', 'send', 'share', 'show', 'sign',
                        'tag', 'take', 'tell', 'think', 'update', 'work', 'write', 'join',
                        'view', 'load']

    # Convert light verb roots to all its forms using lemma lookup
    light_verbs_full = lookup_verbs(light_verb_roots, spacy_lemmas)

    # Combine into a single list of stopwords
    add_stopwords = set(
        combine(
            nltk_stopwords, url_terms, days_of_the_week, months_of_the_year, years,
            time_periods, time_related, common_words, social_media, light_verbs_full
        )
    )

    # Combine all stopwords into one list and export to text file
    combined_stopwords = nltk_stopwords.union(add_stopwords)
    stopword_list = sorted(list(combined_stopwords))
    # Write out stopwords to file
    with open('stopwords.txt', 'w') as f:
        for word in stopword_list:
            f.write(word + '\n')

    print(f"Exported {len(stopword_list)} words to stopword list.")
