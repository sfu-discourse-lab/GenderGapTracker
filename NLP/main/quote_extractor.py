import argparse
import os
import sys
import logging
import traceback
from bson import ObjectId
from statistics import mean
from datetime import datetime, timedelta
from multiprocessing import Pool, cpu_count

import spacy
from nltk import Tree
from config import config
import utils

app_logger = utils.create_logger('quote_extractor', log_dir='logs', logger_level=logging.INFO, file_log_level=logging.INFO)


# Read quote verb list from file and store as a set for fast lookup
with open(config['NLP']['QUOTE_VERBS'], 'r') as f:
    QUOTE_VERBS = set([line.strip() for line in f])


def get_rawtext_files(RAWTEXT_DIR):
    "Get list of raw text files from which to extract quotes"
    rawtext_files = [file for file in os.listdir(RAWTEXT_DIR) if file.endswith("txt")]
    return rawtext_files


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
    final_quotes = find_global_duplicates(all_quotes)
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
            if not quote:
                start = word.i
                quote = True
            else:
                sent = doc[start:word.i + 1]
                verb = get_closest_verb(doc, sent, len(doc))
                if verb is None:
                    verb = ''
                    verb_index = ''
                    speaker = ''
                    speaker_index = '(0,0)'  # Assign non-empty quote-index to avoid breaking parse
                else:
                    speaker = get_closest_speaker(verb)
                    if speaker:
                        speaker_index = get_pretty_index(speaker)
                        speaker = speaker.text
                    else:
                        speaker_index = '(0,0)'  # Assign non-empty quote-index to avoid breaking parse
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


def get_closest_verb(doc, sent, doc_len, threshold=5):
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


def find_global_duplicates(quote_list):
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


def parse_input_files_only():
    """This method is run only if the user specifies the --file-path argument.
       Mainly used for debugging qutoe extraction on raw text files (ignoring any database arguments).
    """
    for input_file in get_rawtext_files(file_path):
        doc_id = input_file.replace(".txt", "")
        try:
            doc_lines = open(os.path.join(file_path, input_file), 'r').readlines()
            doc_text = '\n'.join(doc_lines)
            doc_text = utils.preprocess_text(doc_text)
            doc = nlp(doc_text)
            quotes = extract_quotes(doc_id=doc_id, doc=doc, write_tree=write_quote_trees_in_file)

            for q in quotes:
                print(q)
                print('-' * 50)
        except:
            app_logger.exception("message")
            traceback.print_exc()
    sys.exit(0)


def parse_doc(collection, doc):
    """Perform quote extraction conditionally on one document"""
    try:
        doc_id = str(doc['_id'])

        if doc is None:
            app_logger.error('Document "{0}" not found.'.format(doc_id))
        else:
            text = doc['body']
            text_length = len(text)
            if text_length > MAX_BODY_LENGTH:
                app_logger.warn(
                    'Skipping document {0} due to long length {1} characters'.format(doc['_id'], text_length))
                if update_db:
                    collection.update(
                        {'_id': ObjectId(doc_id)},
                        {
                            '$set': {
                                'lastModifier': 'max_body_len',
                                'lastModified': datetime.now()
                            },
                            '$unset': {
                                'quotes': 1
                            }
                        },
                        upsert=True
                    )
            # Process document
            doc_text = utils.preprocess_text(doc['body'])
            spacy_doc = nlp(doc_text)

            quotes = extract_quotes(doc_id=doc_id, doc=spacy_doc, write_tree=write_quote_trees_in_file)
            if update_db:
                collection.update(
                    {'_id': ObjectId(doc_id)},
                    {'$set': {
                        'quotes': quotes,
                        'lastModifier': 'quote_extractor',
                        'lastModified': datetime.now()}})
            else:
                # If dry run, then display extracted quotes (for testing)
                print('=' * 20, ' Quotes ', '=' * 20)
                for q in quotes:
                    print(q, '\n')
    except:
        app_logger.exception("message")
        traceback.print_exc()


def chunker(iterable, chunksize):
    """Yield a smaller chunk of a large iterable"""
    for i in range(0, len(iterable), chunksize):
        yield iterable[i:i + chunksize]


def parse_chunks(chunk):
    """Pass through a chunk of document IDs and extract quotes"""
    db_client = utils.init_client(MONGO_ARGS)
    collection = db_client[DB_NAME][READ_COL]
    for idx in chunk:
        doc = collection.find_one({'_id': idx}, no_cursor_timeout=True)
        parse_doc(collection, doc)


def run_pool(poolsize, chunksize):
    """Concurrently perform quote extraction based on a filter query"""
    # Find ALL ids in the database within the query bounds (one-time only)
    client = utils.init_client(MONGO_ARGS)
    id_collection = client[DB_NAME][READ_COL]
    query = utils.prepare_query(filters)
    document_ids = id_collection.find(query, no_cursor_timeout=True).distinct('_id')
    app_logger.info("Obtained ID list for {} articles.".format(len(document_ids)))

    # Check for doc limit
    if DOC_LIMIT > 0:
        document_ids = document_ids[:DOC_LIMIT]
    app_logger.info("Processing {} articles...".format(len(document_ids)))

    # Process quotes using a pool of executors 
    pool = Pool(processes=poolsize)
    pool.map(parse_chunks, chunker(document_ids, chunksize=chunksize))
    pool.close()


if __name__ == '__main__':
    # Take in custom user-specified arguments if necessary (otherwise use defaults)
    parser = argparse.ArgumentParser()
    parser.add_argument('--db', type=str, default='mediaTracker', help="Database name")
    parser.add_argument('--readcol', type=str, default='media', help="Collection name")
    parser.add_argument('--dry_run', action='store_true', help="Do not write anything to database (dry run)")
    parser.add_argument('--force_update', action='store_true', help="Overwrite already processed documents in database")
    parser.add_argument('--write_quote_trees', action='store_true', help="Write quote trees to file")
    parser.add_argument('--file_path', type=str, default='', help="Save quote trees to file path")
    parser.add_argument('--output_path', type=str, default='output', help="Save output files to output path")
    parser.add_argument('--limit', type=int, default=0, help="Max. number of articles to process")
    parser.add_argument('--begin_date', type=str, help=" Start date of articles to process (YYYY-MM-DD)")
    parser.add_argument('--end_date', type=str, help=" End date of articles to process (YYYY-MM-DD)")
    parser.add_argument("--outlets", type=str, help="Comma-separated list of news outlets to consider in query scope")
    parser.add_argument('--ids', type=str, help=" Comma-separated list of document ids to process. \
                                                  By default, all documents in the collection are processed.")
    parser.add_argument("--poolsize", type=int, default=cpu_count() + 1, help="Size of the concurrent process pool for the given task")
    parser.add_argument("--chunksize", type=int, default=20, help="Number of articles IDs per chunk being processed concurrently")

    args = vars(parser.parse_args())

    # ========== Parse config params and arguments ==========
    MONGO_ARGS = config['MONGO_ARGS']
    MAX_BODY_LENGTH = config['NLP']['MAX_BODY_LENGTH']

    DB_NAME = args['db']
    READ_COL = args['readcol']
    DOC_LIMIT = args['limit']
    write_quote_trees_in_file = args['write_quote_trees']
    update_db = not args['dry_run']   # Do not update db when we request a dry run
    force_update = args['force_update']
    file_path = args['file_path']
    OUTPUT_DIRECTORY = args['output_path']
    poolsize = args['poolsize']
    chunksize = args['chunksize']

    date_begin = utils.convert_date(args['begin_date']) if args['begin_date'] else None
    date_end = utils.convert_date(args['end_date']) if args['begin_date'] else None

    date_filters = []
    if date_begin:
        date_filters.append({"publishedAt": {"$gte": date_begin}})
    if date_end:
        date_filters.append({"publishedAt": {"$lt": date_end + timedelta(days=1)}})

    if force_update:
        other_filters = []
    else:
        other_filters = [
            {'quotes': {'$exists': False}},
            {'lastModifier': 'mediaCollectors'}]

    doc_id_list = args['ids'] if args['ids'] else None
    outlet_list = args['outlets'] if args['outlets'] else None

    filters = {
        'doc_id_list': doc_id_list,
        'outlets': outlet_list,
        'force_update': force_update,
        'date_filters': date_filters,
        'other_filters': other_filters
    }

    print("Loading spaCy language model...")
    nlp = spacy.load('en_core_web_lg')
    print("Finished loading")
    # Create output directory for quote trees if necessary
    if write_quote_trees_in_file and not os.path.exists(OUTPUT_DIRECTORY):
        os.makedirs(OUTPUT_DIRECTORY)

    if file_path:
        # If an input file path is specified, the code will parse files instead, ignoring database arguments
        # The results are printed to the console
        parse_input_files_only()
    else:
        # Directly parse documents from the db
        run_pool(poolsize, chunksize)
        app_logger.info('Finished processing quotes.')
