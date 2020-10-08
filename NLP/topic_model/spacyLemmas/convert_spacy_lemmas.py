"""
Convert the most recent spaCy lemma dictionary to a format that can be read
by Spark-NLP.
"""
import json
from urllib.request import urlopen


def get_spacy_lemmas():
    """Download most recent spaCy lemma dictionary from their GitHub repo."""
    spacy_lemma_url = "https://raw.githubusercontent.com/explosion/spacy-lookups-data/master/spacy_lookups_data/data/en_lemma_lookup.json"
    with urlopen(spacy_lemma_url) as response:
        lemmas = response.read()
    return json.loads(lemmas)


def get_same_value_keys(spacy_lemmas):
    """Map all duplicate values in the lemma dict to the key that they point to."""
    same_value_keys = {}   
    for key, value in spacy_lemmas.items(): 
        if value not in same_value_keys: 
            same_value_keys[value] = [key] 
        else: 
            same_value_keys[value].append(key) 
    return same_value_keys


def write_sparknlp_lemmas(spacy_lemmas):
    """Write out the lemmas as per Spark NLP's format:
    https://stackoverflow.com/a/57873365/1194761
    """
    same_value_keys = get_same_value_keys(spacy_lemmas)
    with open('spacy_english_lemmas.txt', "w") as f:
        for key, values in same_value_keys.items():
            # Only output values without special characters
            alphabet_values = [val.lower() for val in values if val.isalpha()]
            if key.isalpha():
                f.write("{0} -> {0} {1}\n".format(key.lower(), ' '.join(list(alphabet_values))))


def main():
    spacy_lemmas = get_spacy_lemmas()
    write_sparknlp_lemmas(spacy_lemmas)


if __name__ == "__main__":
    main()
