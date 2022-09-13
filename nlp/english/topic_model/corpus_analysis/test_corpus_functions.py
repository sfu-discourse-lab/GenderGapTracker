"""
Test (experimental script)
Compare two corpora using corpus linguistics techniques. Instead of comparing a study
corpus against a reference corpus, this script performs keyness analysis on one corpus 
with respect to the other, i.e. the result provides the difference between the two corpora
in either direction.

Uses the corpus_toolkit library:
https://github.com/kristopherkyle/corpus_toolkit

NOTE: We modify/override the tokenizer and the dependency bigram functions for better
quality results compared to the base corpus toolkit library.
 * `ct.tokenize` is overriden with the `toknenize` in this file
 * `ct.dep_bigram` is overridden with the `dep_bigram` in this file
"""
import argparse
import os
import spacy
from corpus_toolkit import corpus_tools as ct

# List of punctuation and extraneous symbols/characters to ignore from our data
remove_items = [
    ",", ".", "?", '"', "!", ":", ";", "(", ")", "[", "]", "''",
    "``", "--", "―", "”", "“", "-", "*", "="
]

nlp = spacy.load("en_core_web_sm", disable=['ner'])


def tokenize(corpus, remove_list=remove_items):
    """ Tokenize, lowercase and lemmatize text from a corpus using spaCy. """
    for text in corpus:
        doc = nlp.tokenizer(text)
        tokens = [str(token.lemma_).lower() for token in doc
                  if token.text.lower() not in remove_list]
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
            
    # Return a dictioary of dictionaries
    bigram_dict = {"bi_freq": bi_freq, "dep_freq": dep_freq, "head_freq": head_freq, "range": range_freq, "samples": match_sentences}
    return(bigram_dict)


def get_freq_lists(corpus1, corpus2):
    """ Generate frequency lists for each corpus. """
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


def compare_keyness():
    """ Compare keyness results for female/male source-dominant articles. """
    corp1_freq, corp2_freq = get_freq_lists(corpus1, corpus2)
    # Calculate keyness in first direction
    corp_key_direction_1 = calculate_keyness(corp1_freq, corp2_freq)
    print(f'\n--------Target: {corpus1}, Reference: {corpus2}\n--------')
    ct.head(corp_key_direction_1, hits=20)
    # Calculate keyness in second direction
    corp_key_direction_2 = calculate_keyness(corp2_freq, corp1_freq)
    print(f'\n--------Target: {corpus2}, Reference: {corpus1}\n--------')
    ct.head(corp_key_direction_2, hits=20)


def compare_dep_bigrams():
    """ Calculate dependency bigrams for each corpus and compare them.
    """
    corp1_bg_dict = dep_bigram(ct.ldcorpus(corpus1), "dobj")
    corp2_bg_dict = dep_bigram(ct.ldcorpus(corpus2), "dobj")
    print(f'\n--------Dependency bigrams for: {corpus1}')
    ct.head(corp1_bg_dict["bi_freq"], hits=20)
    print(f'\n--------Dependency bigrams for: {corpus2}')
    ct.head(corp2_bg_dict["bi_freq"], hits=20)


def compare_collocation(word):
    """ Calculate collocates for a particular word in each corpus and compare them.
        Here, we use the built-in tokenizer in corpus_toolkit (simple split by whitespace)
        to avoid removing special characters/punctuations that might be collocates.
    """
    corp1_collocates = ct.collocator(ct.tokenize(ct.ldcorpus(corpus1)), word, stat="MI")
    corp2_collocates = ct.collocator(ct.tokenize(ct.ldcorpus(corpus2)), word, stat="MI")
    print(f'\n--------Collocates for the word `{word}`: {corpus1}')
    ct.head(corp1_collocates, hits=20)
    print(f'\n--------Collocates for the word `{word}`: {corpus2}')
    ct.head(corp2_collocates, hits=20)


def compare_pos_tags(pos):
    """ Calculate POS tags for tokens in each corpus and compare them.
        Specify any of the below spaCy POS tag as the input argument:
           NOUN: common noun
           ADJ: adjective
           VERB: verb
    """
    corp1_tagged_freq = ct.frequency(ct.tag(ct.ldcorpus(corpus1)))
    corp2_tagged_freq = ct.frequency(ct.tag(ct.ldcorpus(corpus2)))
    print(f'\n--------Tagged frequency: {corpus1}')
    corp1_tagged_pos = {key: corp1_tagged_freq[key] for key in corp1_tagged_freq
                        if "_" + pos in key}
    ct.head(corp1_tagged_pos, hits=20)
    print(f'\n--------Tagged frequency: {corpus2}')
    corp2_tagged_pos = {key: corp2_tagged_freq[key] for key in corp2_tagged_freq
                        if "_" + pos in key}
    ct.head(corp2_tagged_pos, hits=20)


def main():
    """ This script is for testing only - select one of the options below (Comment out the rest). """
    # compare_keyness()
    # compare_dep_bigrams()
    compare_collocation('buy')
    # compare_pos_tags('ADJ')


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--topic', '-t', type=str, required=True, help="Topic name to analyze (t1, t2, etc.)")
    parser.add_argument('--filedir', '-f', type=str, required=True, help="Directory of text files for female/male source-dominant corpora")
    parser.add_argument('--limit', '-l', type=str, default=20, help="Number of terms to show in keyness plot")
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
    corpus1 = os.path.join(ROOT, TOPIC, 'female')
    corpus2 = os.path.join(ROOT, TOPIC, 'male')

    # Test run corpus analysis
    main()