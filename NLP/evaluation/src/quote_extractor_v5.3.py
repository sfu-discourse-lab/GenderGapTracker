import argparse
import os
import json
import re
from statistics import mean
import spacy
from nltk import Tree


# Read quote verb list from file and store as a set for fast lookup
with open('quote_verb_list.txt', 'r') as f:
    QUOTE_VERBS = set([line.strip() for line in f])


def string_contains_digit(inputString):
    return bool(re.search(r'\d', inputString))


# ----- Formatting Functions
def get_pretty_index(key):
    """ Format span/token indexes like (123,127) """
    frmt = '({0},{1})'
    if isinstance(key, spacy.tokens.span.Span):
        return frmt.format(key.start_char, key.end_char)
    elif isinstance(key, spacy.tokens.token.Token):
        return frmt.format(key.idx, key.idx + len(key.text))


def prettify(key):
    """ Format span/token like 'Book (7,11)' """
    frmt = '{0} ({1},{2})'

    if isinstance(key, spacy.tokens.span.Span):
        return frmt.format(str(key), key.start_char, key.end_char)
    elif isinstance(key, spacy.tokens.token.Token):
        return frmt.format(str(key), key.idx, key.idx + len(key.text))


def to_nltk_tree(node):
    """ Plot quote trees if required. """
    if node.n_lefts + node.n_rights > 0:
        return Tree(node.orth_, [to_nltk_tree(child) for child in node.children])
    else:
        return node.orth_ + '[' + node.dep_ + ']'


def is_quote_in_sent(quote_set, sent_set):
    """ Check if a detected quote in an specific sentence. """
    quote_len = len(quote_set)
    sent_len = len(sent_set)
    threshold = min(quote_len, sent_len) / 2
    if len(quote_set.intersection(sent_set)) >= threshold:
        return True
    else:
        return False


def sent_in_double_quotes(sent):
    """ Check whether the sentence is in double quotes (potential floating quote). """
    sent_string = str(sent)
    sent_string = sent_string.replace(" ", "")
    sent_string = sent_string.replace("\n", "")
    sent_string = sent_string.replace("\\", "")
    if "\"" in sent_string[0:3] and ".\"" in sent_string[-3:]:
        return True
    else:
        return False


def find_sent_in_double_quotes(doc_sents, i):
    """ When detecting a sentence which is the candidate for start of a floating quote we use this function to
        look into next sentences to see if this floating quote candidate consists of more than one sentence.
    """
    MAX_SENTS_TO_PROCESS = 5
    sent = doc_sents[i]
    sent_string = str(sent)
    sent_string = sent_string.replace(" ", "")
    sent_string = sent_string.replace("\n", "")
    sent_string = sent_string.replace("\\", "")
    sents_processed = 1
    quote_startchar = sent.start_char
    quote_token_count = len(sent)

    if "\"" not in sent_string[0:3]:
        return 1, False, None
    elif "\"" in sent_string[0:3] and ".\"" in sent_string[-3:]:
        quote_endchar = sent.end_char
        quote_obj = {
            'speaker': "",
            'speaker_index': "",
            'quote': str(sent),
            'quote_index': "({0},{1})".format(quote_startchar, quote_endchar),
            'verb': "",
            'verb_index': "",
            'quote_token_count': quote_token_count,
            'quote_type': "QCQ",
            'is_floating_quote': True
        }
        return 1, True, quote_obj

    # Check for quotes in multiple sentences.
    float_quote = str(sent)
    quote_startchar = sent.start_char
    quote_token_count = len(sent)
    # Try to find a floating quote in multiple sentences.
    while (i + sents_processed) < len(doc_sents) and sents_processed < MAX_SENTS_TO_PROCESS:
        next_sent = doc_sents[i + sents_processed]
        next_sent_string = str(next_sent).replace(" ", "").replace("\n", "").replace("\\", "")
        # The last sentence should only have double quotes at the end and not a double quote in the middle or
        # at the beginning
        # In V2.94 added a catch for small closing sentences like: ".\n
        next_sent_has_only_one_quote_at_end = ((len(next_sent_string) < 3) and next_sent_string.count("\"") == 1) or \
                                              (("\"" in next_sent_string[-3:]) and not ("\"" in next_sent_string[0:-3]))
        float_quote += str(next_sent)
        sents_processed += 1
        quote_token_count += len(next_sent)
        if next_sent_has_only_one_quote_at_end:
            quote_endchar = next_sent.end_char
            quote_obj = {
                'speaker': "",
                'speaker_index': "",
                'quote': float_quote,
                'quote_index': "({0},{1})".format(quote_startchar, quote_endchar),
                'verb': "",
                'verb_index': "",
                'quote_token_count': quote_token_count,
                'quote_type': "QCQ",
                'is_floating_quote': True
            }
            return sents_processed, True, quote_obj
    # If we can not capture a floating quote, may be the starting " character is a typo or bad parsing of raw data.
    # It's better to start again from the next sentence.
    return 1, False, None


def is_qcqsv_or_qcqvs_csv(sent, quote_list):
    """ Return whether the given sentence is in a QCQSV, QCQVS or CSV quote. """
    sent_start = sent.start_char
    sent_end = sent.end_char
    sent_set = set(range(sent_start, sent_end))
    for q in quote_list:
        quote_index = (q["quote_index"][1:-1]).split(",")
        quote_index = [int(x) for x in quote_index]
        # Check if quote and sentence have overlap. Because the quote may contain mutiple sentences(?),
        # we do not check if the quote contains the sentence of vice versa
        quote_set = set(range(quote_index[0], quote_index[1]))
        if is_quote_in_sent(quote_set, sent_set):
            quote_type = q["quote_type"]
            if quote_type in ["QCQSV", "QCQVS", "CSV"]:
                return True, q

    return False, None


def extract_quotes(doc_id, doc, write_tree=False):
    """ Steps to extract quotes in a document:
        1. Extract syntactic quotes
        2. Extract floating quotes
        3. Extract heuristic quotes (using custom rules)
    """
    syntactic_quotes = extract_syntactic_quotes(doc_id, doc, write_tree)
    floating_quotes = extract_floating_quotes(doc, syntactic_quotes)
    heuristic_quotes = extract_heuristic_quotes(doc)
    all_quotes = syntactic_quotes + floating_quotes + heuristic_quotes
    final_quotes = remove_duplicate_quotes(all_quotes)
    return final_quotes


def extract_syntactic_quotes(doc_id, doc, write_tree=False):
    """ Extract syntactic quotes. """

    quote_list = []
    if write_tree:
        tree_writer = open(os.path.join(OUTPUT_DIRECTORY, doc_id + '_quoteTree.txt'), 'w')
    for word in doc:
        if word.dep_ in ('ccomp'):
            if (word.right_edge.i + 1) < len(doc):
                subtree_span = doc[word.left_edge.i: word.right_edge.i + 1]
                sent = subtree_span
                verb = subtree_span.root.head
                nodes_to_look_for_nsubj = [x for x in subtree_span.root.head.children] + [x for x in
                                                                                          subtree_span.root.head.head.children]
                # for child in subtree_span.root.head.children:
                for child in nodes_to_look_for_nsubj:
                    if child.dep_ == 'nsubj' and verb.text.lower() in QUOTE_VERBS:
                        if child.right_edge.i + 1 < len(doc):
                            subj_subtree_span = doc[child.left_edge.i: child.right_edge.i + 1]
                            speaker = subj_subtree_span
                            if type(speaker) == spacy.tokens.span.Span:
                                # Get quote type
                                quote_type = get_quote_type(doc, sent, verb, speaker, subtree_span)
                                # Filter invalid quotes (mostly floating quotes detected with invalid speaker/verb)
                                is_valid_speaker = str(speaker).strip().lower() not in ["i", "we"]
                                is_valid_type = not (quote_type[0] == "Q" and quote_type[-1] == "Q")
                                is_valid_quote = len(str(sent).strip()) > 0

                                if is_valid_quote and is_valid_type and is_valid_speaker:
                                    quote_obj = {
                                        'speaker': str(speaker),
                                        'speaker_index': get_pretty_index(speaker),
                                        'quote': str(sent),
                                        'quote_index': get_pretty_index(sent),
                                        'verb': str(verb),
                                        'verb_index': get_pretty_index(verb),
                                        'quote_token_count': len(sent),
                                        'quote_type': quote_type,
                                        'is_floating_quote': False
                                    }
                                    quote_list.append(quote_obj)
                                    if write_tree:
                                        tree_writer.writelines(
                                            '{0}\n{1}\n{0}\n'.format('-' * (len(str(sent)) + 1),
                                                                     str(sent).replace('\n', ' ')))
                                        to_nltk_tree(subtree_span.root.head).pretty_print(stream=tree_writer)
                                break
        elif word.dep_ in ('prep'):
            expression = doc[word.head.left_edge.i: word.i + 1]
            if (expression.text in ('according to', 'According to')):
                accnode = word.head
                tonode = word
                # subtree_span = doc[word.head.left_edge.i : word.right_edge.i + 1]
                if (accnode.i < accnode.head.i):
                    sent = doc[accnode.right_edge.i + 1: accnode.head.right_edge.i + 1]
                    speaker = doc[tonode.i + 1: accnode.right_edge.i + 1]
                else:
                    sent = doc[accnode.head.left_edge.i: accnode.i]
                    speaker = doc[tonode.i + 1: accnode.head.right_edge.i + 1]
                # print("Speaker:", str(speaker), " Content:", str(sent))

                # if is_valid_quote and is_valid_type and is_valid_speaker:
                # TODO: How to validate these quotes? what is the quote type?
                quote_obj = {
                    'speaker': str(speaker),
                    'speaker_index': get_pretty_index(speaker),
                    'quote': str(sent),
                    'quote_index': get_pretty_index(sent),
                    'verb': 'according to',
                    'verb_index': get_pretty_index(expression),
                    'quote_token_count': len(sent),
                    'quote_type': "AccordingTo",
                    'is_floating_quote': False
                }
                quote_list.append(quote_obj)
                if write_tree:
                    sent_str = str(sent)
                    tree_writer.writelines(
                        '{0}\n{1}\n{0}\n'.format('-' * (len(sent_str) + 1), sent_str.replace('\n', ' ')))
                    to_nltk_tree(subtree_span.root.head).pretty_print(stream=tree_writer)
    return quote_list


def extract_heuristic_quotes(doc):
    """Extract quotes that are enclosed between start and end quotation marks

    :param Doc doc: SpaCy Doc object of the whole news file
    :returns: List of quote objects containing the quotes and other information
    """
    quote_list = []
    quote = False
    for word in doc:
        if str(word) == '"':
            if quote == False:
                start = word.i
                quote = True
            else:
                sent = doc[start:word.i + 1]
                verb = get_closest_verb(doc, sent, len(doc))
                if verb is None:
                    verb = ''
                    verb_index = ''
                    speaker = ''
                    speaker_index = '(0,0)' # Assign non-empty quote-index to avoid breaking parse
                else:
                    speaker = get_closest_speaker(verb)
                    if speaker:
                        speaker_index = get_pretty_index(speaker)
                        speaker = speaker.text
                    else:
                        speaker_index = '(0,0)' # Assign non-empty quote-index to avoid breaking parse
                        speaker = ''
                    verb_index = get_pretty_index(verb)
                    verb = verb.text
                if len(sent) > 6 and len(sent) < 100:
                    quote_obj = {
                        'speaker': speaker,
                        'speaker_index': speaker_index,
                        'quote': str(sent),
                        'quote_index': get_pretty_index(sent),
                        'verb': verb,
                        'verb_index': verb_index,
                        'quote_token_count': len(sent),
                        'quote_type': "Heuristic",
                        'is_floating_quote': False
                    }
                    quote_list.append(quote_obj)
                quote = False
    return quote_list


def get_closest_speaker(verb):
    """ Get the closest speaker associated with a quoting verb
    
    :params token verb: SpaCy token object that contains the verb
    :return: The selected speaker(spaCy token object) or None
    """
    for child in verb.children:
        if child.dep_ == 'nsubj':
            return child
    return None


def get_closest_verb(doc, sent, doc_len, threshold=3):
    """ Get the closest verb associated with a quote

    :params Doc doc: SpaCy Doc object of the whole news file
    :params Span sent: SpaCy Span object that contains the quote
    :params int doc_len: Length of the entire SpaCy Doc
    :params int threshold: Threshold for window to search in
    :return: The selected verb(spaCy token object) or None
    """
    for i in range(sent.start - 1, sent.start - threshold, -1):
        if doc[i].pos_ == 'VERB' and doc[i].text not in ('is', 'was', 'be'):
            return doc[i]
        elif doc[i].text in ['.', '"']:
            break
    for i in range(sent.end, min(sent.end + threshold, doc_len), 1):
        if doc[i].pos_ == 'VERB' and doc[i].text not in ('is', 'was', 'be'):
            return doc[i]
        elif doc[i].text in ['.', '"']:
            break
    return None


def remove_duplicate_quotes(quote_list):
    """ Find duplicate quotes and remove them

    :params lst quote_list: List of quote objects which contain many auxillary attributes
    :return: List of de-duplicated quote objects
    """
    quote_span_list = []
    new_quote_span_list = []
    remove_quotes = []
    for quote in quote_list:
        span = list(map(int, quote['quote_index'][1:-1].split(',')))
        quote_span_list.append([span[0], span[1]])
    for quote_idx, (start, end) in enumerate(quote_span_list):
        quote_range = range(start, end)
        not_duplicate = True
        if len(quote_list[quote_idx]['quote'].split(' ')) < 4:
            remove_quotes.append(quote_idx)
            continue
        for ref_quote_idx, (ref_start, ref_end) in enumerate(new_quote_span_list):
            ref_quote_range = range(ref_start, ref_end)
            if len(set(quote_range).intersection(ref_quote_range)) > 0:
                not_duplicate = False
                remove_quotes.append(quote_idx)
                break
        if not_duplicate:
            new_quote_span_list.append([start, end])

    final_quote_list = []
    for idx, quote in enumerate(quote_list):
        if idx not in remove_quotes:
            final_quote_list.append(quote)
    return final_quote_list


def extract_floating_quotes(doc, syntactic_quotes):
    """ Extract floating quotes. """
    floating_quotes = []
    doc_sents = [x for x in doc.sents]
    if len(doc_sents) > 0:
        last_sent = doc_sents[0]
        i = 1
        while i < len(doc_sents):
            sent = doc_sents[i]
            # Check if there is a QCQSV or QCQVS quote before this sentence.
            # The speaker and verb of this quote (if exists) will be used for possible floating quote
            sent_is_after_qcqsv_or_qcqvs_csv, last_quote = is_qcqsv_or_qcqvs_csv(last_sent, syntactic_quotes)

            if sent_is_after_qcqsv_or_qcqvs_csv:
                # Search for sentence(s) in double quotes
                sents_processed, found_floating_quote, floating_quote = find_sent_in_double_quotes(doc_sents, i)
            else:
                # start processing next sentence.
                sents_processed = 1
                floating_quote = str(sent)
                found_floating_quote = None
            # Increment sentence index
            i += sents_processed
            if sent_is_after_qcqsv_or_qcqvs_csv and found_floating_quote:
                floating_quote['speaker'] = last_quote['speaker']
                floating_quote['speaker_index'] = last_quote['speaker_index']
                floating_quotes.append(floating_quote)

            last_sent = sent
    return floating_quotes


def get_quote_type(doc, quote, verb, speaker, subtree_span):
    """ Determine quote type based on relative placement of quote, verb and speaker. """
    dc1_pos = -1
    dc2_pos = -1
    quote_starts_with_quote = False
    quote_ends_with_quote = False

    if (doc[max(0, quote.start - 1)].is_quote or doc[quote.start].is_quote) and \
            (doc[quote.end].is_quote or doc[min(len(doc) - 1, quote.end + 1)].is_quote):
        quote_starts_with_quote = True
        quote_ends_with_quote = True
        dc1_pos = max(0, quote.start_char - 1)
        dc2_pos = quote.end_char + 1
    elif doc[max(0, subtree_span.start - 1)].is_quote and doc[min(len(doc) - 1, subtree_span.end + 1)].is_quote:
        quote_starts_with_quote = True
        quote_ends_with_quote = True
        dc1_pos = max(0, subtree_span.start_char - 1)
        dc2_pos = subtree_span.end_char + 1
    elif speaker.start < quote.start and doc[max(0, speaker.start - 1)].is_quote and doc[
        min(len(doc) - 1, subtree_span.end + 1)].is_quote:
        quote_starts_with_quote = True
        quote_ends_with_quote = True
        dc1_pos = max(0, speaker.start_char - 1)
        dc2_pos = subtree_span.end_char + 1

    content_pos = mean([quote.start_char, quote.end_char])
    verb_pos = mean([verb.idx, verb.idx + len(str(verb))])
    speaker_pos = mean([speaker.start_char, speaker.end_char])

    if quote_starts_with_quote and quote_ends_with_quote:
        letters = ["Q", "q", "C", "V", "S"]
        indices = [dc1_pos, dc2_pos, content_pos, verb_pos, speaker_pos]
    else:
        letters = ["C", "V", "S"]
        indices = [content_pos, verb_pos, speaker_pos]

    # Sort the Q,C,S,V letters based on the placement of quota mark, content, speaker and verb
    keydict = dict(zip(letters, indices))
    letters.sort(key=keydict.get)
    return "".join(letters).replace('q', 'Q')


def preprocess_text(txt):
    txt = txt.replace(u'\xa0', u' ')
    txt = txt.replace(u'\xe9', u' ')
    # To fix the problem of not breaking at \n
    txt = txt.replace("\n", ".\n ")
    # To remove potential duplicate dots
    txt = txt.replace("..\n ", ".\n ")
    txt = txt.replace(". .\n ", ".\n ")
    txt = txt.replace("  ", " ")
    # Replace double quotes
    txt = txt.replace("”", '"')
    txt = txt.replace("“", '"')
    # ---
    txt = txt.replace("〝", '"')
    txt = txt.replace("〞", '"')
    return txt


def get_rawtext_files(RAWTEXT_DIR):
    "Create rawText files using article body"
    rawtext_files = [file for file in os.listdir(RAWTEXT_DIR) if file.endswith("txt")]
    return rawtext_files


def main(rawtext_files):
    for filename in rawtext_files:
        try:
            doc_lines = open(os.path.join(RAWTEXT_DIR, filename), 'r').readlines()
            doc_text = ''.join(doc_lines)
            doc_text = preprocess_text(doc_text)
            doc_coref = nlp(doc_text)
            quotes = extract_quotes(doc_id=filename.strip('.txt'), doc=doc_coref, write_tree=False)

            all_quotes = quotes

            with open(os.path.join(OUTPUT_DIRECTORY, filename.strip('.txt') + ".json"), 'w') as f:
                json.dump(all_quotes, f, indent=4, ensure_ascii=False)

            for q in all_quotes:
                print(q)
                print('-' * 50)

        except Exception as e:
            print("Exception: {}".format(e))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--lang", type=str, default="en_core_web_lg", help="spaCy language model to use")
    parser.add_argument("--input", type=str, default="./data/rawtext", help="Path to raw news article data")
    parser.add_argument("--output", type=str, default="./validation/V5.1", help="Path to raw news article data")
    args = parser.parse_args()

    # Define paths
    RAWTEXT_DIR = args.input
    OUTPUT_DIRECTORY = args.output
    if not os.path.exists(OUTPUT_DIRECTORY):
        os.makedirs(OUTPUT_DIRECTORY)

    print("Loading spaCy language model '{}'".format(args.lang))
    nlp = spacy.load(args.lang)

    main(get_rawtext_files(RAWTEXT_DIR))
