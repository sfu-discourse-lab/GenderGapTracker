import argparse
import logging
import re
import traceback
import urllib
from bson import ObjectId
from datetime import datetime, timedelta
import requests
from multiprocessing import Pool, cpu_count

import neuralcoref
import spacy
from spacy.pipeline import EntityRuler
from config import config
import utils

app_logger = utils.create_logger('entity_gender_annotator_logger', log_dir='logs', logger_level=logging.INFO, file_log_level=logging.INFO)

# ========== Named Entity Merging functions ==========

# merge nes is a two step unification process:
# 1- Merge NEs based on exact match
# 2- merge NEs based on partial match
def merge_nes(doc_coref):
    # ne_dict and ne_cluster are dictionaries which keys are PERSON named entities extracted from the text and values
    #  are mentions of that named entity in the text. Mention clusters come from coreference clustering algorithm.
    ne_dict = {}
    ne_clust = {}
    # It's highly recommended to clean nes before merging them. They usually contain invalid characters
    person_nes = [x for x in doc_coref.ents if x.label_ == 'PERSON']
    # in this for loop we try to merge clusters detected in coreference clustering

    # ----- Part A: assign clusters to person named entities
    for ent in person_nes:
        # Sometimes we get noisy characters in name entities
        # TODO: Maybe it's better to check for other types of problems in NEs here too

        ent_cleaned = utils.clean_ne(str(ent))
        if (len(ent_cleaned) == 0) or utils.string_contains_digit(ent_cleaned):
            continue

        ent_set = set(range(ent.start_char, ent.end_char))
        found = False
        # if no coreference clusters is detected in the document
        if doc_coref._.coref_clusters is None:
            ne_dict[ent] = []
            ne_clust[ent] = -1

        else:
            for cluster in doc_coref._.coref_clusters:
                for ment in cluster.mentions:
                    ment_set = set(range(ment.start_char, ment.end_char))
                    if has_coverage(ent_set, ment_set):
                        ne_dict[ent] = cluster
                        ne_clust[ent] = cluster.i

                        found = True
                        break
                # End of for on mentions
                if found:
                    break

            # End of for on clusters

            if not found:
                ne_dict[ent] = []
                ne_clust[ent] = -1

    # ----- Part B: Merge clusters in ne_dict based on exact match of their representative (PERSON named entities)
    merged_nes = {}
    for ne, cluster in zip(ne_dict.keys(), ne_dict.values()):

        ne_clean_text = utils.clean_ne(str(ne))

        if not cluster:
            cluster_id = [-1]
            mentions = []
        else:
            cluster_id = [cluster.i]
            mentions = cluster.mentions

        # check if we already have a unique cluster with same representative
        if ne_clean_text in merged_nes.keys():
            retrieved = merged_nes[ne_clean_text]
            lst = retrieved['mentions']
            lst = lst + [ne] + mentions
            cls = retrieved['cluster_id']
            cls = cls + cluster_id
            merged_nes[ne_clean_text] = {'mentions': lst, 'cluster_id': cls}
        else:
            tmp = [ne] + mentions
            merged_nes[ne_clean_text] = {'mentions': tmp, 'cluster_id': cluster_id}

    # ----- Part C: do a complex merge
    complex_merged_nes, changed = complex_merge(merged_nes)

    return complex_merged_nes


# This is the last try to merge named entities based on multi-part ne merge policy
def complex_merge(ne_dict):
    merged_nes = {}
    changed = {}
    for ne in ne_dict.keys():
        found = False
        for merged in merged_nes.keys():
            if can_merge_nes(str(ne), str(merged)):
                if len(ne) > len(merged):
                    merged_nes[ne] = merged_nes[merged] + ne_dict[ne]['mentions']
                    changed[ne] = 1
                    del merged_nes[merged]
                elif len(ne) < len(merged):
                    changed[merged] = 1
                    merged_nes[merged] = merged_nes[merged] + ne_dict[ne]['mentions']

                found = True

                break
        if not found:
            changed[ne] = 0
            merged_nes[ne] = ne_dict[ne]['mentions']

    return merged_nes, changed


def has_coverage(s1, s2):
    return len(s1.intersection(s2)) >= 2


# This function checks whether we can do maltipart merge for two named entities.
def can_merge_nes(ne1, ne2):
    can_merge = False
    # To get rid of \n and empty tokens
    ne1 = ne1.strip()
    ne2 = ne2.strip()
    if len(ne1) > len(ne2):
        ne_big = ne1
        ne_small = ne2
    else:
        ne_big = ne2
        ne_small = ne1

    ne_big = ne_big.split(' ')
    ne_small = ne_small.split(' ')

    # Check for merging a two part name with a one part first name
    if len(ne_big) == 2 and len(ne_small) == 1:
        first_name_match = (ne_big[0] == ne_small[0]) and \
                            ne_big[0][0].isupper() and \
                            ne_small[0][0].isupper() and \
                            ne_big[1][0].isupper()

        can_merge = first_name_match
    # Check for merging a three part and a two part
    elif len(ne_big) == 3 and len(ne_small) == 2:
        last_middle_name_match = (ne_big[-1] == ne_small[-1]) and \
                                 (ne_big[-2] == ne_small[-2]) and \
                                  ne_big[0][0].isupper() and \
                                  ne_big[1][0].isupper() and \
                                  ne_big[2][0].isupper()
        can_merge = last_middle_name_match
    # Check for merging a three part and a one part
    elif len(ne_big) == 3 and len(ne_small) == 1:
        last_name_match = (ne_big[-1] == ne_small[-1]) and \
                           ne_big[-1][0].isupper() and \
                           ne_big[0][0].isupper()

        can_merge = last_name_match

    app_logger.debug('ne1: {0}\tne2: {1}\tComplex Merge Result: {2}'.format(ne1, ne2, can_merge))

    return can_merge


def remove_invalid_nes(unified_nes):
    final_nes = {}
    for key, value in zip(unified_nes.keys(), unified_nes.values()):
        # to remove one part NEs after merge
        # Todo: should only remove singltones?
        representative_has_one_token = (len(key.split(' ')) == 1)
        key_is_valid = not (representative_has_one_token)
        if key_is_valid:
            final_nes[key] = value

    return final_nes


def get_named_entity(doc_coref, span_start, span_end):
    span_set = set(range(span_start, span_end))

    for x in doc_coref.ents:
        x_start = x.start_char
        x_end = x.end_char
        x_set = set(range(x_start, x_end))
        if has_coverage(span_set, x_set):
            return str(x), x.label_

    return None, None


# This function assignes quotes to nes based on overlap of quote's speaker span and the names entity span
def quote_assign(nes, quotes, doc_coref):
    quote_nes = {}
    quote_no_nes = []
    index_finder_pattern = re.compile(r'.*\((\d+),(\d+)\).*')

    aligned_quotes_indices = []

    for q in quotes:
        regex_match = index_finder_pattern.match(q['speaker_index'])
        q_start = int(regex_match.groups()[0])
        q_end = int(regex_match.groups()[1])
        q_set = set(range(q_start, q_end))

        quote_aligned = False
        # search in all of the named entity mentions in it's cluster for the speaker span.
        for ne, mentions in zip(nes.keys(), nes.values()):
            if quote_aligned:
                break
            for mention in mentions:
                mention_start = mention.start_char
                mention_end = mention.end_char
                mention_set = set(range(mention_start, mention_end))

                if has_coverage(q_set, mention_set):
                    alignment_key = '{0}-{1}'.format(q_start, q_end)
                    aligned_quotes_indices.append(alignment_key)
                    q['is_aligned'] = True
                    q['named_entity'] = str(ne)
                    q['named_entity_type'] = 'PERSON'
                    quote_aligned = True

                    if ne in quote_nes.keys():
                        current_ne_quotes = quote_nes[ne]
                        current_ne_quotes.append(q)
                        quote_nes[ne] = current_ne_quotes
                    else:
                        quote_nes[ne] = [q]

                    break  # Stop searching in mentions. Go for next quote

        if not quote_aligned:
            q['is_aligned'] = False
            ne_text, ne_type = get_named_entity(doc_coref, q_start, q_end)
            if ne_text is not None:
                q['named_entity'] = ne_text
                q['named_entity_type'] = ne_type
            else:
                q['named_entity'] = ''
                q['named_entity_type'] = 'UNKNOWN'

            quote_no_nes.append(q)

    all_quotes = []
    for ne, q in zip(quote_nes.keys(), quote_nes.values()):
        all_quotes = all_quotes + q

    all_quotes = all_quotes + quote_no_nes

    return quote_nes, quote_no_nes, all_quotes


# TODO: How to consider quotes_no_nes in voices?
def measure_voices(people_genders, nes_quotes, quotes_no_nes):
    voice_females = 0
    voice_males = 0
    voice_unknowns = 0

    for person, quotes in zip(nes_quotes.keys(), nes_quotes.values()):
        gender = people_genders[person]

        sum_of_quote_lengths = 0
        for q in quotes:
            sum_of_quote_lengths += q['quote_token_count']

        if gender == 'female':
            voice_females += sum_of_quote_lengths
        elif gender == 'male':
            voice_males += sum_of_quote_lengths
        else:
            voice_unknowns += sum_of_quote_lengths

    return voice_females, voice_males, voice_unknowns


# ========== Main functions ==========

def get_pronoun_based_gender(unified_nes):
    result_dict = {}
    for person, mentions in zip(unified_nes.keys(), unified_nes.values()):
        female_count = 0
        male_count = 0
        for mention in mentions:
            if str(mention).lower() in ['she', 'her']:
                female_count += 1
            elif str(mention).lower() in ['he', 'his']:
                male_count += 1

        # Now we calculate final result
        prob = 0
        if male_count > female_count:
            gender = 'male'
            prob = male_count / (female_count + male_count)
        elif female_count > male_count:
            gender = 'female'
            prob = female_count / (male_count + female_count)
        else:
            gender = 'unknown'  # in case of a tie or zero pronoun mentions
            prob = 0

        result_dict[person] = {'gender': gender, 'male_count': male_count, 'female_count': female_count,
                               'probability': prob}

    return result_dict


def get_genders(session, names):
    parsed_names = urllib.parse.quote(','.join(names))
    url = "{0}/get-genders?people={1}".format(GENDER_RECOGNITION_SERVICE, parsed_names)
    if parsed_names:
        response = session.get(url)
        if response:
            data = response.json()
        else:
            code = response.status_code
            app_logger.warning("Failed to retrieve valid JSON: status code {}".format(code))
            data = {}
    else:
        data = {}
    return data


def update_existing_collection(collection, doc, session):
    """If user does not specify the `writecol` argument, write entity-gender results to existing collection."""
    doc_id = str(doc['_id'])
    text = doc['body']

    # Process authors
    cleaner = utils.CleanAuthors(nlp)
    authors = cleaner.clean(doc['authors'], blocklist)
    author_genders = get_genders(session, authors)

    authors_female = []
    authors_male = []
    authors_unknown = []

    for person, gender in zip(author_genders.keys(), author_genders.values()):
        if gender == 'female':
            authors_female.append(person)
        elif gender == 'male':
            authors_male.append(person)
        else:
            if person:
                authors_unknown.append(person)

    quotes = doc['quotes']
    text_preprocessed = utils.preprocess_text(text)
    doc_coref = nlp(text_preprocessed)
    unified_nes = merge_nes(doc_coref)
    final_nes = remove_invalid_nes(unified_nes)

    # Process people
    people = list(final_nes.keys())
    people = list(filter(None, people))  # Make sure no empty values are sent for gender prediction
    people_genders = get_genders(session, people)

    people_female = []
    people_male = []
    people_unknown = []
    for person, gender in zip(people_genders.keys(), people_genders.values()):
        if gender == 'female':
            people_female.append(person)
        elif gender == 'male':
            people_male.append(person)
        else:
            if person:
                people_unknown.append(person)

    # Expert fields are filled base on gender of speakers in the quotes
    sources_female = []
    sources_male = []
    sources_unknown = []

    nes_quotes, quotes_no_nes, all_quotes = quote_assign(final_nes, quotes, doc_coref)
    sources = list(nes_quotes.keys())

    for speaker in sources:
        gender = people_genders[speaker]
        if gender == 'female':
            sources_female.append(speaker)
        elif gender == 'male':
            sources_male.append(speaker)
        else:
            if speaker:
                sources_unknown.append(speaker)

    voices_female, voices_male, voices_unknowns = measure_voices(people_genders, nes_quotes, quotes_no_nes)

    article_type = utils.get_article_type(doc.get('url', ""))

    collection.update(
        {'_id': ObjectId(doc_id)},
        {'$set': {
            'people': people,
            'peopleCount': len(people),
            'peopleFemale': people_female,
            'peopleFemaleCount': len(people_female),
            'peopleMale': people_male,
            'peopleMaleCount': len(people_male),
            'peopleUnknown': people_unknown,
            'peopleUnknownCount': len(people_unknown),
            'sources': sources,
            'sourcesCount': len(sources),
            'sourcesFemale': sources_female,
            'sourcesFemaleCount': len(sources_female),
            'sourcesMale': sources_male,
            'sourcesMaleCount': len(sources_male),
            'sourcesUnknown': sources_unknown,
            'sourcesUnknownCount': len(sources_unknown),
            'authorsAll': authors,
            'authorsMale': authors_male,
            'authorsMaleCount': len(authors_male),
            'authorsFemale': authors_female,
            'authorsFemaleCount': len(authors_female),
            'authorsUnknown': authors_unknown,
            'authorsUnknownCount': len(authors_unknown),
            'voicesFemale': voices_female,
            'voicesMale': voices_male,
            'voicesUnknown': voices_unknowns,
            'quoteCount': len(quotes),
            'speakersNotCountedInSources': len(quotes_no_nes),
            'quotesUpdated': all_quotes,
            'articleType': article_type,
            'lastModifier': 'entity_gender_annotator',
            'lastModified': datetime.now()}})


def add_new_collection(collection, doc, session):
    """If user specifies the `writecol` argument, write entity-gender results to a new collection."""
    doc_id = str(doc['_id'])
    text = doc['body']
    # Process authors
    cleaner = utils.CleanAuthors(nlp)
    authors = cleaner.clean(doc['authors'], blocklist)
    author_genders = get_genders(session, authors)

    authors_female = []
    authors_male = []
    authors_unknown = []

    for person, gender in zip(author_genders.keys(), author_genders.values()):
        if gender == 'female':
            authors_female.append(person)
        elif gender == 'male':
            authors_male.append(person)
        else:
            if person:
                authors_unknown.append(person)

    quotes = doc['quotes']
    text_preprocessed = utils.preprocess_text(text)
    doc_coref = nlp(text_preprocessed)
    unified_nes = merge_nes(doc_coref)
    final_nes = remove_invalid_nes(unified_nes)

    # Process people
    people = list(final_nes.keys())
    people = list(filter(None, people))  # Make sure no empty values are sent for gender prediction
    people_genders = get_genders(session, people)

    people_female = []
    people_male = []
    people_unknown = []
    for person, gender in zip(people_genders.keys(), people_genders.values()):
        if gender == 'female':
            people_female.append(person)
        elif gender == 'male':
            people_male.append(person)
        else:
            if person:
                people_unknown.append(person)

    # Expert fields are filled base on gender of speakers in the quotes
    sources_female = []
    sources_male = []
    sources_unknown = []

    nes_quotes, quotes_no_nes, all_quotes = quote_assign(final_nes, quotes, doc_coref)
    sources = list(nes_quotes.keys())

    for speaker in sources:
        gender = people_genders[speaker]
        if gender == 'female':
            sources_female.append(speaker)
        elif gender == 'male':
            sources_male.append(speaker)
        else:
            if speaker:
                sources_unknown.append(speaker)

    voices_female, voices_male, voices_unknowns = measure_voices(people_genders, nes_quotes, quotes_no_nes)

    article_type = utils.get_article_type(doc.get('url', ""))

    collection.insert_one(
        {
            'currentId': ObjectId(doc_id),
            'people': people,
            'peopleCount': len(people),
            'peopleFemale': people_female,
            'peopleFemaleCount': len(people_female),
            'peopleMale': people_male,
            'peopleMaleCount': len(people_male),
            'peopleUnknown': people_unknown,
            'peopleUnknownCount': len(people_unknown),
            'sources': sources,
            'sourcesCount': len(sources),
            'sourcesFemale': sources_female,
            'sourcesFemaleCount': len(sources_female),
            'sourcesMale': sources_male,
            'sourcesMaleCount': len(sources_male),
            'sourcesUnknown': sources_unknown,
            'sourcesUnknownCount': len(sources_unknown),
            'authorsAll': authors,
            'authorsMale': authors_male,
            'authorsMaleCount': len(authors_male),
            'authorsFemale': authors_female,
            'authorsFemaleCount': len(authors_female),
            'authorsUnknown': authors_unknown,
            'authorsUnknownCount': len(authors_unknown),
            'voicesFemale': voices_female,
            'voicesMale': voices_male,
            'voicesUnknown': voices_unknowns,
            'quoteCount': len(quotes),
            'speakersNotCountedInSources': len(quotes_no_nes),
            'quotesUpdated': all_quotes,
            'articleType': article_type,
            'lastModifier': 'entity_gender_annotator',
            'lastModified': datetime.now(),
        }
    )


def update_db(read_collection, write_collection, doc, session):
    """Write entity-gender annotation results to a new collection OR update the existing collection.
    """
    doc_id = str(doc['_id'])
    try:
        text = doc['body']
        text_length = len(text)
        if text_length > MAX_BODY_LENGTH:
            app_logger.warn(
                'Skipping document {0} due to long length {1} characters'.format(doc_id, text_length))
            read_collection.update(
                {'_id': ObjectId(doc_id)},
                {'$unset': {
                    'people': 1,
                    'peopleCount': 1,
                    'peopleFemale': 1,
                    'peopleFemaleCount': 1,
                    'peopleMale': 1,
                    'peopleMaleCount': 1,
                    'peopleUnknown': 1,
                    'peopleUnknownCount': 1,
                    'sources': 1,
                    'sourcesCount': 1,
                    'sourcesFemale': 1,
                    'sourcesFemaleCount': 1,
                    'sourcesMale': 1,
                    'sourcesMaleCount': 1,
                    'sourcesUnknown': 1,
                    'sourcesUnknownCount': 1,
                    'authorsAll': 1,
                    'authorsMale': 1,
                    'authorsMaleCount': 1,
                    'authorsFemale': 1,
                    'authorsFemaleCount': 1,
                    'authorsUnknown': 1,
                    'authorsUnknownCount': 1,
                    'voicesFemale': 1,
                    'voicesMale': 1,
                    'voicesUnknown': 1,
                    'quoteCount': 1,
                    'speakersNotCountedInSources': 1,
                    'quotesUpdated': 1,
                    'articleType': 1,
                    'lastModifier': 'max_body_len',
                    'lastModified': datetime.now()}})
        else:
            if WRITE_COL:
                add_new_collection(write_collection, doc, session)
            else:
                update_existing_collection(read_collection, doc, session)

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
    read_collection = db_client[DB_NAME][READ_COL]
    write_collection = db_client[DB_NAME][WRITE_COL] if WRITE_COL else None
    # Create requests session object for more persistent HTTP connections
    session = requests.Session()
    for idx in chunk:
        doc = read_collection.find_one({'_id': idx}, no_cursor_timeout=True)
        update_db(read_collection, write_collection, doc, session)


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
    parser.add_argument('--readcol', type=str, default='media', help="Read collection name")
    parser.add_argument('--writecol', type=str, default='', help="Write collection name")
    parser.add_argument('--force_update', action='store_true', help="Overwrite already processed documents in database")
    parser.add_argument('--limit', type=int, default=0, help="Max number of articles to process")
    parser.add_argument('--genderapi_token', type=str, default=config['GENDER_RECOGNITION']['GENDERAPI_TOKEN'], help="Specify genderapi token")
    parser.add_argument('--gr_ip', type=str, default=config['GENDER_RECOGNITION']['HOST'], help="Specify gender recognition host IP address")
    parser.add_argument('--gr_port', type=int, default=config['GENDER_RECOGNITION']['PORT'], help="Specify gender recognition port number")
    parser.add_argument('--begin_date', type=str, help="Start date of articles to process (YYYY-MM-DD)")
    parser.add_argument('--end_date', type=str, help="End date of articles to process (YYYY-MM-DD)")
    parser.add_argument("--outlets", type=str, help="Comma-separated list of news outlets to consider in query scope")
    parser.add_argument('--ids', type=str, help="Comma-separated list of document ids to process. \
                                                 By default, all documents in the collection are processed.")
    parser.add_argument("--poolsize", type=int, default=cpu_count() + 1, help="Size of the concurrent process pool for the given task")
    parser.add_argument("--chunksize", type=int, default=20, help="Number of articles IDs per chunk being processed concurrently")

    args = vars(parser.parse_args())

    # ========== Parse config params and arguments ==========
    MONGO_ARGS = config['MONGO_ARGS']
    AUTHOR_BLOCKLIST = config['NLP']['AUTHOR_BLOCKLIST']
    NAME_PATTERNS = config['NLP']['NAME_PATTERNS']
    MAX_BODY_LENGTH = config['NLP']['MAX_BODY_LENGTH']

    DB_NAME = args['db']
    READ_COL = args['readcol']
    WRITE_COL = args['writecol']
    GENDER_IP = args['gr_ip']
    GENDER_PORT = args['gr_port']
    DOC_LIMIT = args['limit']
    force_update = args['force_update']
    poolsize = args['poolsize']
    chunksize = args['chunksize']

    date_begin = utils.convert_date(args['begin_date']) if args['begin_date'] else None
    date_end = utils.convert_date(args['end_date']) if args['begin_date'] else None

    date_filters = []
    if date_begin:
        date_filters.append({"publishedAt": {"$gte": date_begin}})
    if date_end:
        date_filters.append({"publishedAt": {"$lt": date_end + timedelta(days=1)}})

    GENDER_RECOGNITION_SERVICE = 'http://{}:{}'.format(GENDER_IP, GENDER_PORT)

    if force_update:
        other_filters = [
            {'quotes': {'$exists': True}}
        ]
    else:
        other_filters = [
            {'quotes': {'$exists': True}},
            {'lastModifier': 'quote_extractor'},
            {'quotesUpdated': {'$exists': False}}
        ]

    doc_id_list = args['ids'] if args['ids'] else None
    outlet_list = args['outlets'] if args['outlets'] else None

    filters = {
        'doc_id_list': doc_id_list,
        'outlets': outlet_list,
        'force_update': force_update,
        'date_filters': date_filters,
        'other_filters': other_filters
    }

    blocklist = utils.get_author_blocklist(AUTHOR_BLOCKLIST)

    print('Loading spaCy language model...')
    nlp = spacy.load('en_core_web_lg')
    # Add custom named entity rules for non-standard person names that spaCy doesn't automatically identify
    ruler = EntityRuler(nlp, overwrite_ents=True).from_disk(NAME_PATTERNS)
    nlp.add_pipe(ruler)
    print('Finished loading.')

    coref = neuralcoref.NeuralCoref(nlp.vocab, max_dist=200)
    nlp.add_pipe(coref, name='neuralcoref')

    run_pool(poolsize, chunksize)
    app_logger.info('Finished processing entities.')
    