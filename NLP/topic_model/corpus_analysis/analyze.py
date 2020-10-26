"""
Perform a comparative analysis using techniques from corpus linguistics.

Uses the corpus_toolkit library:
https://github.com/kristopherkyle/corpus_toolkit

Full credit to the original author @kkyle2 (Kristopher Kyle).
"""

import argparse
import spacy
from corpus_toolkit import corpus_tools as ct
import os
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
sns.set_style('whitegrid', {'axes.grid': False})
params = {
    'legend.fontsize': 'large',
    'axes.labelsize': 15,
    'axes.titlesize': 15,
    'xtick.labelsize': 15,
    'ytick.labelsize': 15,
    'axes.titlepad': 15,
    'figure.titlesize': 15,
}
plt.rcParams.update(params)

# Load spaCy model for tokenization, tagging and parsing
nlp = spacy.load("en_core_web_sm", disable=['ner'])

# List of punctuation and extraneous symbols/characters to ignore from our data
remove_items = [
    ",", ".", "?", '"', "!", ":", ";", "(", ")", "[", "]", "''",
    "``", "--", "―", "”", "“", "*", "="
]
# Useless bigrams that we don't want to display in our plots
useless_bigrams = ['photo_open', 'page_send', 'more_read']


def load_lemma(lemma_file):
    """ Override the default lemmatizer in corpus-toolkit (written by Kristopher Kyle).
        We want to use spaCy's lemmas, so we reformat the tokens accordingly.
    """
    lemma_dict = {}
    lemma_list = open(lemma_file, errors="ignore").read()
    lemma_list = lemma_list.replace("->", "")  # Replace marker, if it exists
    lemma_list = lemma_list.split("\n")
    for line in lemma_list:
        tokens = line.split()
        if len(tokens) <= 2:
            continue
        lemma = tokens[0]   # The lemma is the first item on the list
        for token in tokens[1:]:
            if token in lemma_dict:
                continue
            else:
                lemma_dict[token] = lemma
    return lemma_dict


def tokenize(corpus, remove_list=remove_items):
    """ Tokenize, lowercase and lemmatize text from a corpus using spaCy. """
    for text in corpus:
        doc = nlp.tokenizer(text)
        # We only care about lemmatized, lowercased tokens longer than one character
        tokens = [str(token.lemma_).lower() for token in doc
                  if token.is_alpha
                  and token.text.lower() not in remove_list
                  and len(token.text) > 1]
        yield(tokens)
    

def dep_bigram(corpus, dep, lemma=True, lower=True, pron=False, dep_upos=None, head_upos=None, dep_text=None, head_text=None):
    """ Overriding the original method in the corpus_toolkit library because the original
        had a bug in the lowercasing option flag.
    """
    bi_freq, dep_freq, head_freq, range_freq = {}, {}, {}, {}
    match_sentences = []

    def dicter(item, d):
        # d is a dictionary
        if item not in d: 
            d[item] = 1
        else:
            d[item] += 1

    textid = 0
    for text in corpus:
        textid += 1
        range_list = []
        doc = nlp(text)   # Tokenize, tag, and parse text using spaCy
        for sentence in doc.sents:
            index_start = 0
            sent_text = []
            dep_headi = []
            first_token = True

            for token in sentence:   # Iterate through tokens in document
                if first_token:
                    index_start = token.i  # If this is the first token, set the index start number
                    first_token = False    # Then set first token to False

                sent_text.append(token.text)

                if token.dep_ == dep:  # If the token's dependency tag matches the one designated
                    dep_tg = token.pos_  # Get upos tag for the dependent (only used if dep_upos is specified)
                    head_tg = token.head.pos_  # Get upos tag for the head (only used if dep_upos is specified)

                    if lemma:  # If lemma is true, use lemma form of dependent and head
                        if not pron:  # If we don't want Spacy's pronoun lemmatization
                            if token.lemma_ == "-PRON-":
                                dependent = token.text.lower()  # Then use the raw form of the word
                                headt = token.head.text.lower()
                            else:
                                if lower:
                                    dependent = token.lemma_.lower()
                                    headt = token.head.lemma_.lower()
                                else:  # If lower is false, don't lower
                                    dependent = token.lemma_
                                    headt = token.head.lemma_

                        else:  # If we want Spacy's pronoun lemma
                            dependent = token.lemma_
                            headt = token.head.lemma_
                    
                    if not lemma:  # If lemma is false, use exact token representation
                        if lower:
                            dependent = token.text.lower()
                            headt = token.head.text.lower()
                        else:
                            dependent = token.text
                            headt = token.head.text
    
                    if dep_upos is not None and dep_upos != dep_tg:  # If dependent tag is specified and upos doesn't match, skip item
                        continue
                    
                    if head_upos is not None and head_upos != head_tg:  # If head tag is specified and upos doesn't match, skip item
                        continue
    
                    if dep_text is not None and dep_text != dependent:  # If dependent text is specified and text doesn't match, skip item
                        continue
                    
                    if head_text is not None and head_text != headt:  # If head text is specified and text doesn't match, skip item
                        continue
    
                    dep_headi.append([token.i - index_start, token.head.i - index_start])  # Add sentence-level index numbers for dependent and head

                    dep_bigram = dependent + "_" + headt  # Create dependency bigram
        
                    range_list.append(dep_bigram)
                    dicter(dep_bigram, bi_freq)
                    dicter(dependent, dep_freq)
                    dicter(headt, head_freq)
        
            ## This section is for creating a list of sentences that include our hits
            for x in dep_headi:
                # Because there may be multiple hits in each sentence (but we only want to display one hit at at time),
                # we make a temporary copy of the sentence that we will modify
                temp_sent = sent_text.copy()
                
                depi = sent_text[x[0]] + "_" + dep + "_dep"  # e.g., word_dobj_dep
                headi = sent_text[x[1]] + "_" + dep + "_head"  # e.g., word_dobj_head
                
                temp_sent[x[0]] = depi   # Change dependent word to depi in temporary sentence
                temp_sent[x[1]] = headi  # Change head word to headi in temporary sentence
                
                temp_sent.append(str(textid))      # Add file inded to sent to indicate where example originated
                match_sentences.append(temp_sent)  # Add temporary sentence to match_sentences for output
        
        #create a type list of the dep_bigrams in the text
        for x in list(set(range_list)):
            dicter(x, range_freq)  # Add document counts to the range_freq dictionary
    
    # NOTE: We pop useless bigrams from the dict (specific to our news corpus in GGT)
    for bg in useless_bigrams:
        bi_freq.pop(bg, None)

    # Return a dictioary of dictionaries
    bigram_dict = {"bi_freq": bi_freq, "dep_freq": dep_freq, "head_freq": head_freq, "range": range_freq, "samples": match_sentences}
    return(bigram_dict)


def get_freq_lists(corpus1, corpus2):
    """ Generate frequency lists for each corpus. 
        Note that we use our customized spaCy tokenizer and not the
        one built into corpus_toolkit (for better quality tokenization).
    """
    corp1_freq = ct.frequency(tokenize(ct.ldcorpus(corpus1),
                                       remove_list=remove_items))
    corp2_freq = ct.frequency(tokenize(ct.ldcorpus(corpus2),
                                       remove_list=remove_items))
    return corp1_freq, corp2_freq


def calculate_keyness(corp1_freq, corp2_freq):
    """ Calculate keyness for corpora in either direction (1 vs. 2 and 2 vs. 1).
        Takes in the frequency lists for each corpus to compute the keyness.
    """
    corp_key = ct.keyness(corp1_freq, corp2_freq, effect="log-ratio")
    return corp_key


def score_keyness():
    """ Return a dictionary of keyness results.
        The top values (positive) of the dictionary contain keyness indices for corpus #1
        as the study corpus, while the bottom values (negative) contain the keyness
        indices for corpus #2 as the study corpus.
    """
    corp1_freq, corp2_freq = get_freq_lists(corpus1, corpus2)
    # Calculate keyness in first direction
    corp_key = calculate_keyness(corp1_freq, corp2_freq)
    corp_key = sorted(corp_key.items(),
                      key=lambda kv: kv[1],
                      reverse=True)
    return corp_key


def score_dep_bigrams():
    """ Calculate dependency bigrams for each corpus and compare them.
        Note that we use our override `dep_bigram` function from this file
        rather than the original one in corpus_toolkit because of a bug in the
        original version (0.29, where lowercasing wasn't working in `ct.dep_bigrams`)
    """
    corp1_dict = dep_bigram(ct.ldcorpus(corpus1), "dobj")
    corp2_dict = dep_bigram(ct.ldcorpus(corpus2), "dobj")
    corp1_bigrams = sorted(
        corp1_dict['bi_freq'].items(),
        key=lambda kv: kv[1],
        reverse=True
    )
    corp2_bigrams = sorted(
        corp2_dict['bi_freq'].items(),
        key=lambda kv: kv[1],
        reverse=True
    )
    return corp1_bigrams, corp2_bigrams


def plot_keyness(female_corp_df, male_corp_df):
    """ Create a lollipop plot of keyness results showing the comparison of the
        two corpora.
    """
    fig, (ax1, ax2) = plt.subplots(ncols=2, sharey=False, figsize=(8, 5))
    ax1.hlines(y=male_corp_df['key'], xmin=0, xmax=male_corp_df['keyness_index'], color='#004d72', linewidths=0.5)
    ax1.plot(male_corp_df['keyness_index'], male_corp_df['key'], 'o', color='#004d72')
    ax1.set_xlim(min(male_corp_df['keyness_index']) - 1, 0)
    ax1.set_xlabel('Keyness index')
    ax1.set_title('Male corpus')

    ax2.hlines(y=female_corp_df['key'], xmin=0, xmax=female_corp_df['keyness_index'], color='#af1858', linewidths=0.5)
    ax2.plot(female_corp_df['keyness_index'], female_corp_df['key'], 'o', color='#af1858')
    ax2.set_xlim(0, max(female_corp_df['keyness_index']) + 1)
    ax2.set_xlabel('Keyness index')
    ax2.yaxis.tick_right()
    ax2.set_title('Female corpus')

    if not os.path.exists("Plots"):
        os.makedirs("Plots")
    plotname = f"{ROOT.split('/')[-1]}_{TOPIC}.png"
    plt.suptitle('Keyness')
    plt.tight_layout(rect=[0, 0.01, 1, 0.95])
    os.makedirs("Plots/keyness", exist_ok=True)
    fig.savefig(os.path.join("Plots", "keyness", plotname))
    print("Finished.. Exported keyness plot to `Plots/keyness`")


def plot_dep_bigrams(female_corp_df, male_corp_df):
    """ Create a lollipop plot of keyness results showing the comparison of the
        two corpora.
    """
    fig, (ax1, ax2) = plt.subplots(ncols=2, sharey=False, figsize=(8, 5))
    ax1.hlines(y=male_corp_df['bigram'], xmin=0, xmax=male_corp_df['frequency'], color='#004d72', linewidths=0.5)
    ax1.plot(male_corp_df['frequency'], male_corp_df['bigram'], 'o', color='#004d72')
    ax1.set_xlim(0, max(male_corp_df['frequency']) + 1)
    ax1.set_xlabel('Frequency')
    ax1.set_title('Male corpus')

    ax2.hlines(y=female_corp_df['bigram'], xmin=0, xmax=female_corp_df['frequency'], color='#af1858', linewidths=0.5)
    ax2.plot(female_corp_df['frequency'], female_corp_df['bigram'], 'o', color='#af1858')
    ax2.set_xlim(0, max(female_corp_df['frequency']) + 2)
    ax2.set_xlabel('Frequency')
    ax2.yaxis.tick_right()
    ax2.yaxis.grid(which='major', color='#d3d3d3', linestyle='--', linewidth=0.5)
    ax2.set_title('Female corpus')

    if not os.path.exists("Plots"):
        os.makedirs("Plots")
    plotname = f"{ROOT.split('/')[-1]}_{TOPIC}.png"
    plt.suptitle('Dependency bigrams')
    plt.tight_layout(rect=[0, 0.01, 1, 0.95])
    os.makedirs("Plots/dep_bigrams", exist_ok=True)
    fig.savefig(os.path.join("Plots", "dep_bigrams", plotname))
    print("Finished.. Exported dependency bigrams plot to `Plots/dep_bigrams`")


def run_keyness_pipeline():
    keys = score_keyness()
    female_corpus_keys = dict(keys[:LIMIT])
    male_corpus_keys = dict(keys[-LIMIT:])
    # Convert key dicts to Pandas DataFrames for plotting
    female_corp_df = pd.DataFrame([female_corpus_keys]).transpose().reset_index()
    female_corp_df.columns = ['key', 'keyness_index']
    female_corp_df = female_corp_df.sort_values(by='keyness_index')
    male_corp_df = pd.DataFrame([male_corpus_keys]).transpose().reset_index()
    male_corp_df.columns = ['key', 'keyness_index']
    male_corp_df = male_corp_df.sort_values(by='keyness_index', ascending=False)
    # Plot results
    plot_keyness(female_corp_df, male_corp_df)


def run_dep_bigram_pipeline():
    corp1_bigrams, corp2_bigrams = score_dep_bigrams()
    female_dep_bigrams = dict(corp1_bigrams[:LIMIT])
    male_dep_bigrams = dict(corp2_bigrams[:LIMIT])
    # Convert key dicts to Pandas DataFrames for plotting
    female_corp_df = pd.DataFrame([female_dep_bigrams]).transpose().reset_index()
    female_corp_df.columns = ['bigram', 'frequency']
    female_corp_df = female_corp_df.sort_values(by='frequency')
    male_corp_df = pd.DataFrame([male_dep_bigrams]).transpose().reset_index()
    male_corp_df.columns = ['bigram', 'frequency']
    male_corp_df = male_corp_df.sort_values(by='frequency')
    # Plot results
    plot_dep_bigrams(female_corp_df, male_corp_df)


def main():
    run_keyness_pipeline()   # We always run the keyness pipeline comparing two corpora
    # Below are optional
    if run_dependency_bigram:
        run_dep_bigram_pipeline()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--topic', '-t', type=str, required=True, help="Topic name to analyze (t1, t2, etc.)")
    parser.add_argument('--filedir', '-f', type=str, required=True, help="Directory of text files for female/male source-dominant corpora")
    parser.add_argument('--limit', '-l', type=str, default=20, help="Number of terms to show in keyness plot")
    parser.add_argument('--dep_bigrams', action='store_true', help="Plot dependency bigrams tp compare two corpora, if required")
    args = parser.parse_args()

    if os.path.exists(args.filedir) and os.path.isdir(args.filedir):
        if not os.listdir(args.filedir):
            parser.error("Unable to find text files in `{}`. Please check that it is not empty.".format(args.filedir))
        else:    
            ROOT = args.filedir
    else:
        print("Could not find directory {}. Please check it exists.".format(args.filedir))
        
    TOPIC = args.topic
    LIMIT = args.limit
    run_dependency_bigram = args.dep_bigrams
    corpus1 = os.path.join(ROOT, TOPIC, 'female')
    corpus2 = os.path.join(ROOT, TOPIC, 'male')

    lemma_dict = load_lemma('spacyLemmas/spacy_english_lemmas.txt')

    # Run keyness analysis
    main()