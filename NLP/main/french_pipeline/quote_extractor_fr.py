import datetime
import getopt
import logging
import os
import sys
import traceback
import pymongo
import spacy
from statistics import mean
from bson import ObjectId
from spacy.tokens import Span
from nltk import Tree
import re
import math
import json

nlp = spacy.load('fr_core_news_md')
START_GUILLEMETS = set()
END_GUILLEMETS = set()

if not os.path.exists('logs'):
    os.makedirs('logs')

logging.basicConfig(filename='logs/quote-extractor.log', format='%(asctime)s %(levelname)-8s %(message)s',
                    level=logging.INFO, datefmt='%Y-%m-%d %H:%M:%S')

"""

selon PERSON
d'après PERSON

argue: faire valoir
argued: a fait valoir, ont fait valoir
argues: fait valoir, font valoir
faire remarquer, (a; ont) fait remarquer; (fait; font) remarquer

laisser tomber, (a; ont) laissé tomber, laisse(nt) tomber

se questionner, (s'est; se sont) questionné(e; s; es), questionne(nt)
s'exprimer, (s'est, se sont) exprimé(e; s; es), s'exprime(nt)
se désoler, (s'est; se sont) désolé(e; s; es), se désole(nt)
se consoler, (s'est; se sont) consolé(e; s; es), se console(nt)
se lamenter, (s'est; se sont) lamenté(e; s; es), se lamente(nt)
s'interroger, (s'est; se sont) interrogé(e; s; es); s'interroge(nt)

"""

quoteVerbWhiteList = ['reconnaitre', 'ajouter', 'admettre', 'annoncer', 'croire', 'prétendre', 'soutenir',
                      'conclure', 'confirmer', 'déclarer', 'décrire', 'assurer', 'expliquer', 'trouver',
                      'indiquer', 'informer', 'insister', 'noter', 'souligner', 'prédire', 'fournir',
                      'divulger', 'rappeler', 'répondre', 'dire', 'rapporter', 'répondre', 'affirmer',
                      'suggérer', 'attester', 'penser', 'gazouiller', 'tweeter', 'avertir', 'écrire'] + [
                      'révéler', 'commenter', 'avouer', 'raconter', 'prévenir', 'prédire', 'redouter',
                      'soulever', 'préciser', 'résumer', 'juger', 'estimer', 'dancer', 'lancer', 
                      'nuancer', 'relever', 'constater', 'réclamer', 'remarquer', 'confier', 'observer',
                      'réagir', 'concéder', 'témoigner', 'louanger', 'demander', 'arguer', 'protester',
                      'critiquer', 'plaider', 'poursuivre', 'trancher', 'mentionner', 'souhaiter']

db_client = None
server = None
media_tracker_collection = None


# ----- DB Functions
def init(MONGO_SERVERS, MONGO_USER, MONGO_PASS):
    _db_client = pymongo.MongoClient(MONGO_SERVERS, 27017, username=MONGO_USER, password=MONGO_PASS)
    return _db_client, None


def prepare_query(doc_id, force_update=False):
    if doc_id is not None:
        query = {'_id': ObjectId(doc_id)}

    elif force_update:
        query = {
            '$and':
                [
                    {
                        'outlet':
                            {
                                '$in': ['NationalPost', 'The Globe And Mail', 'TheStar', 'HuffingtonPost',
                                        'Global News',
                                        'CTVNews', 'CBC News']
                            }
                    },
                    {
                        'body': {'$ne': ''}
                    }
                ]
        }
    else:
        query = {
            '$and':
                [
                    {
                        'outlet':
                            {
                                '$in': ['NationalPost', 'The Globe And Mail', 'TheStar', 'HuffingtonPost',
                                        'Global News', 'CTVNews', 'CBC News']
                            }
                    },
                    {
                        'body': {'$ne': ''}
                    },
                    {
                        'quotes': {'$exists': False}
                    }
                ]
        }

    return query


# ----- Formatting Functions
def get_pretty_index(key):
    frmt = '({0},{1})'
    if isinstance(key, spacy.tokens.span.Span):
        return frmt.format(key.start_char, key.end_char)
    elif isinstance(key, spacy.tokens.token.Token):
        return frmt.format(key.idx, key.idx + len(key.text))


def prettify(key):
    frmt = '{0} ({1},{2})'

    if isinstance(key, spacy.tokens.span.Span):
        return frmt.format(str(key), key.start_char, key.end_char)
    elif isinstance(key, spacy.tokens.token.Token):
        return frmt.format(str(key), key.idx, key.idx + len(key.text))


def to_nltk_tree(node):
    if node.n_lefts + node.n_rights > 0:
        return Tree(node.orth_, [to_nltk_tree(child) for child in node.children])
    else:
        return node.orth_ + '[' + node.dep_ + ']'


# ----- Other

def preprocess_text(txt):
    txt = txt.replace(u'\xa0', u' ')

    # To fix the problem of not breaking at \n
    txt = txt.replace("\n", ".\n ")
    # To remove potential duplicate dots
    txt = txt.replace("..\n ", ".\n ")
    txt = txt.replace(". .\n ", ".\n ")
    txt = txt.replace("  ", " ")
    # Replace double quotes
    txt = txt.replace("”",'"')
    txt = txt.replace("“",'"')
    # ---
    txt = txt.replace("〝",'"')
    txt = txt.replace("〞",'"')
    # Replace single quotes
    #txt = txt.replace("‘","'")
    #txt = txt.replace("’",''')
    
    # Note positions of all start and end guillemets
    for match in re.finditer('«', txt):
        START_GUILLEMETS.add(match.start())
    for match in re.finditer('»', txt):
        END_GUILLEMETS.add(match.end())
    
    # Replace guillemets
    txt = txt.replace("«",'"')
    txt = txt.replace("»",'"')
    return txt

# ----- Helper functions

def seenBefore(regex_match, quote_objects):
    quotations = set([eval(quote_obj['quote_index']) for quote_obj in quote_objects])
    
    for q in quotations:
        if fuzzy_match(regex_match.start(), int(q[0])) and fuzzy_match(regex_match.end(), int(q[1])):
            # It's a match, so disregard it
            return True
    return False

def fuzzy_match(num1, num2):
    return abs(num1 - num2) < 3

def getSentenceNumber(sentence_dict, char):
    keys_subset = [k for k in sentence_dict.keys() if k <= char]
    assert len(keys_subset) > 0
    sentence_char = max(keys_subset)
    return sentence_dict[sentence_char]

def getClosestPreceding(preceding_dict, char):
    keys_subset = [k for k in preceding_dict.keys() if k <= char]
    if len(keys_subset) > 0:
        return max(keys_subset)
    else:
        return -1

def getClosestFollowing(following_dict, char):
    keys_subset = [k for k in following_dict.keys() if k >= char]
    if len(keys_subset) > 0:
        return min(keys_subset)
    else:
        return -1
    
def hasAlpha(text):
    for letter in text:
        if letter.isalpha():
            return True
    return False


# ----- Quotation Extraction Functions
def extract_quotes(doc_id, doc, write_tree=False):
    syntactic_quotes = extract_syntactic_quotes(doc_id, doc, write_tree)
    reversed_quotes = extract_reversed_quotes(doc_id, doc, syntactic_quotes, write_tree)
    selon_quotes = extract_selon_quotes(doc_id, doc, syntactic_quotes + reversed_quotes, write_tree)
    floating_quotes = extract_floating_quotes(doc, syntactic_quotes + reversed_quotes + selon_quotes)
    one_sided_quotes = extract_one_sided_quotes(doc, syntactic_quotes + reversed_quotes + selon_quotes + floating_quotes)

    return syntactic_quotes + reversed_quotes + selon_quotes + floating_quotes + one_sided_quotes


def extract_syntactic_quotes(doc_id, doc, write_tree=False):
    quote_list = []
    if write_tree:
        tree_writer = open(os.path.join(OUTPUT_DIRECTORY, doc_id + '.txt'), 'w')
    for word in doc:
        if word.dep_ in ('ccomp'):
            subtree_span = doc[word.left_edge.i: word.right_edge.i + 1]
#             print(word.dep_, '|', subtree_span.text, '|', subtree_span.root.head.text)
            sent = subtree_span
            sent_str = str(sent)
            verb = subtree_span.root.head
            speaker = ""
            for child in subtree_span.root.head.children:
                #print(verb.lemma_.lower())
                if (child.dep_ == 'nsubj') and (verb.lemma_.lower() in quoteVerbWhiteList):
                    subj_subtree_span = doc[child.left_edge.i: child.right_edge.i + 1]
                    speaker = subj_subtree_span
                    if type(speaker) == spacy.tokens.span.Span:
                        quote_length = len(sent)
                        speaker_index = get_pretty_index(speaker)
                        quote_type = get_quote_type(doc, sent, verb, speaker, subtree_span)
                        # Filter invalid quotes (mostly floating quotes detected with invalid speaker/verb)

                        is_valid_speaker = str(speaker).strip().lower() not in ["je","nous"]
                        is_valid_type = not (quote_type[0] == "Q" and quote_type[-1] == "Q")
                        is_valid_quote = len(sent_str.strip()) > 0
                        if (is_valid_quote and is_valid_type and is_valid_speaker):
                        #if is_valid_type:
                            quote_obj = {
                                'speaker': str(speaker),
                                'speaker_index': speaker_index,
                                'quote': sent_str,
                                'quote_index': get_pretty_index(sent),
                                'verb': str(verb),
                                'verb_index': get_pretty_index(verb),
                                'quote_token_count': quote_length,
                                'quote_type': quote_type,
                                'is_floating_quote': False,
                                'reference': str(speaker)
                            }
                            quote_list.append(quote_obj)

                            if write_tree:
                                tree_writer.writelines(
                                    '{0}\n{1}\n{0}\n'.format('-' * (len(sent_str) + 1), sent_str.replace('\n', ' ')))
                                quote_tree_string = to_nltk_tree(subtree_span.root.head).pretty_print(
                                    stream=tree_writer)
                        break
    return quote_list


def extract_reversed_quotes(doc_id, doc, syntactic_quotes, write_tree=False):
    quote_list = []
    
    if write_tree:
        tree_writer = open(os.path.join(OUTPUT_DIRECTORY, doc_id + '.txt'), 'w')
        
    # Named entity preprocessing
    # Create a named entity dictionary by sentence
    named_people_dict = {}
    for ent in doc.ents:
        if ent.label_ == 'PER':
            named_people_dict[ent.start_char] = ent
    
    # spaCy wrappers
    # Create a dictionary of sentences, sentence numbers, indexed by start character
    sentence_dict = {}
    for i,sent in enumerate(doc.sents):
        sentence_dict[sent.start_char] = i,sent
        
    # Noun chunk preprocessing
    # Create a dictionary of noun chunks indexed by start character
    noun_chunk_dict = {}
    for noun_chunk in doc.noun_chunks:
        noun_chunk_dict[noun_chunk.start_char] = noun_chunk
    
    for token in doc:
        if (token.pos_ == 'PRON') and (token.idx not in noun_chunk_dict.keys()):
            span = doc[token.i : token.i+1]
            #print(span)
            noun_chunk_dict[span.start_char] = span
    
    # Find list of quotes with quotation marks
    regex_quotes = []
    # Prune according to existing list of syntactic quotes (fuzzy match)
    for match in re.finditer('(?<=")[^"]+(?=")', doc.text):
        # ignore quotes that don't start or end with the right kind of quote char
        if match.start()-1 not in START_GUILLEMETS:
            continue
        if match.end()+1 not in END_GUILLEMETS:
            continue
            
        #print(match.start(), match.end())
        if not seenBefore(match, syntactic_quotes):
            regex_quotes.append(match)
    
    for q in regex_quotes:
        # Find the sentence of the extracted quotes (with high probability, all tokens will be same sentence)
        sentence_number, _ = getSentenceNumber(sentence_dict,
                                               q.start())
        sentence_number_end, _ = getSentenceNumber(sentence_dict,
                                                   q.end())
        
        span = doc.char_span(q.start()-1, q.end()+1)
        quote_token_count = len(span)
        
        # TODO: DELETE
#         if span is not None:
            
#         else:
#             quote_token_count = len(q.group(0).split(' '))
        
        # Find the closest named person following the sentence to link if possible
        closest_person_start_char = getClosestFollowing(named_people_dict,
                                                          q.end())

        closest_person_sentence_number_end = -1
        
        if closest_person_start_char != -1:
            closest_person_sentence_number, _ = getSentenceNumber(sentence_dict,
                                                              closest_person_start_char)
        
            closest_person_sentence_number_end, _ = getSentenceNumber(sentence_dict,
                                                                      named_people_dict[closest_person_start_char].end_char)
        
            #print('DEBUG:', sentence_number, sentence_number_end, closest_person_sentence_number, closest_person_sentence_number_end)
        
            # Best case scenario: named person and the end of quote are in the same sentence
            if closest_person_sentence_number == sentence_number_end:
                person = named_people_dict[closest_person_start_char]
                #print(q.start(), q.end(), sentence_number, person)
                
                quote_obj = {
                    'speaker': person.text,
                    'speaker_index': '({0},{1})'.format(person.start_char, person.end_char),
                    'quote': span.text,
                    'quote_index': '({0},{1})'.format(q.start()-1, q.end()+1),
                    'verb': '',
                    'verb_index': '',
                    'quote_token_count': quote_token_count,
                    'quote_type': 'QCQVS',
                    'is_floating_quote': False,
                    'reference': noun_chunk.text
                }
                
                quote_list.append(quote_obj)
                continue
        
        # Otherwise try to find a noun phrase in the sentence - Doc.noun_chunks (e.g., "la mairesse de Bobigny")
        closest_noun_chunk_start_char = getClosestFollowing(noun_chunk_dict,
                                                            q.end())
        
        if closest_noun_chunk_start_char != -1:
            closest_noun_chunk_sentence_number, _ = getSentenceNumber(sentence_dict,
                                                                      closest_noun_chunk_start_char)
        
            closest_noun_chunk_sentence_number_end, _ = getSentenceNumber(sentence_dict,
                                                                          noun_chunk_dict[closest_noun_chunk_start_char].end_char)
        
            #print('DEBUG:', sentence_number, sentence_number_end, closest_noun_chunk_sentence_number, closest_noun_chunk_sentence_number_end)
        
            # Best case scenario: noun chunk and the end of quote are in the same sentence
            if closest_noun_chunk_sentence_number == sentence_number_end:
                noun_chunk = noun_chunk_dict[closest_noun_chunk_start_char]
                #print(q.start(), q.end(), sentence_number, noun_chunk)
                
                quote_obj = {
                    'speaker': noun_chunk.text,
                    'speaker_index': '({0},{1})'.format(noun_chunk.start_char, noun_chunk.end_char),
                    'quote': q.group(0),
                    'quote_index': '({0},{1})'.format(q.start(), q.end()),
                    'verb': '',
                    'verb_index': '',
                    'quote_token_count': quote_token_count,
                    'quote_type': 'QCQVS',
                    'is_floating_quote': False,
                    'reference': noun_chunk.text
                }
                
                quote_list.append(quote_obj)
                continue
        
        # Otherwise leave it for the floating quote stage
    
    return quote_list


def extract_floating_quotes(doc, quotations):
    
    floating_quotes = []
    
    regex_quotes = []
    for match in re.finditer('(?<=")[^"]+(?=")', doc.text):
        # ignore quotes that don't start or end with the right kind of quote char
        if match.start()-1 not in START_GUILLEMETS:
            continue
        if match.end()+1 not in END_GUILLEMETS:
            continue
            
        if not seenBefore(match, quotations):
            regex_quotes.append(match)
    
    # spaCy wrappers
    # Create a dictionary of sentences, sentence numbers, indexed by start character
    sentence_dict = {}
    for i,sent in enumerate(doc.sents):
        sentence_dict[sent.start_char] = i,sent
        
    # Create a dictionary of quotes, indexed by final character
    quotation_dict = {}
    for quotation in quotations:
        indices = []
        for index in ['quote_index', 'verb_index', 'speaker_index']:
            if len(quotation[index]) > 0:
                indices.append(eval(quotation[index])[1])

        quotation_dict[max(indices)] = quotation['speaker']
    
    for q in regex_quotes:
        
        previous_quotation_index = getClosestPreceding(quotation_dict, q.start())
        assert previous_quotation_index < q.start()
        
        if previous_quotation_index != -1:
            candidate_speaker = quotation_dict[previous_quotation_index]
            #print(candidate_speaker)
            
            span = doc.text[previous_quotation_index:q.start()]
            assert span is not None
            #print(previous_quotation_index, q.start())
            
            if not hasAlpha(span):
                try:
                    span = doc.char_span(q.start()-1, q.end()+1)
                    quote_token_count = len(span)
                except TypeError:
                    print(q.start(), q.end())

                quote_obj = {
                    'speaker': '',
                    'speaker_index': '',
                    'quote': span.text,
                    'quote_index': '({0},{1})'.format(q.start()-1, q.end()+1),
                    'verb': '',
                    'verb_index': '',
                    'quote_token_count': quote_token_count,
                    'quote_type': 'QCQ',
                    'is_floating_quote': True,
                    'reference': candidate_speaker
                }

                floating_quotes.append(quote_obj)

    return floating_quotes


def stripWithIndices(string, start_index, end_index):
    _string = ''
    for i,letter in enumerate(string):
        if letter.isspace():
            continue
        _string = string[i:]
        start_index = start_index + i
        break
        
    for i,letter in enumerate(reversed(_string)):
        if letter.isspace():
            continue
        string = _string[:len(_string) - i]
        end_index = end_index - i
        break
        
    return string, start_index, end_index


def extract_selon_quotes(doc_id, doc, previous_quotes, write_tree=False):
    quote_list = []
    
    if write_tree:
        tree_writer = open(os.path.join(OUTPUT_DIRECTORY, doc_id + '.txt'), 'w')
        
    # Named entity preprocessing
    # Create a named entity dictionary by sentence
    named_people_dict = {}
    for ent in doc.ents:
        if ent.label_ == 'PER':
            named_people_dict[ent.start_char] = ent
        
    # Noun chunk preprocessing
    # Create a dictionary of noun chunks indexed by start character
    noun_chunk_dict = {}
    for noun_chunk in doc.noun_chunks:
        noun_chunk_dict[noun_chunk.start_char] = noun_chunk
    
    for token in doc:
        if (token.pos_ == 'PRON') and (token.idx not in noun_chunk_dict.keys()):
            span = doc[token.i : token.i+1]
            #print(span)
            noun_chunk_dict[span.start_char] = span
    
    # Find list of quotes with quotation marks
    selon_quotes = []
    # Prune according to existing list of syntactic quotes (fuzzy match)
    for match in re.finditer("\s*([^\.\n]*([\s^](?:[sS]elon|[Dd]'après)\s)[^\.\n]*)\s*", doc.text):
        if not seenBefore(match, previous_quotes):
            selon_quotes.append(match)
    
    for q in selon_quotes:
#         print(q)
        # Find the closest named person following the sentence to link if possible
        closest_person_start_char = getClosestFollowing(named_people_dict,
                                                          q.start())
        # Find a noun phrase in the sentence - Doc.noun_chunks (e.g., "la mairesse de Bobigny")
        closest_noun_chunk_start_char = getClosestFollowing(noun_chunk_dict,
                                                            q.start())
        
        if closest_person_start_char != -1:
            person = named_people_dict[closest_person_start_char]
        elif closest_person_start_char != -1:
            person = noun_chunk_dict[closest_noun_chunk_start_char]
        else:
            #print(q)
            continue
            
        # Figuring out the quote_content
        beforeSelon = doc.text[q.start(1):q.start(2)]
        stripped, start_index, end_index = stripWithIndices(beforeSelon, q.start(1), q.start(2))
        if hasAlpha(stripped):
            quote_content = stripped
            quote_content_start = start_index
            quote_content_end = end_index
                        
            span = doc.char_span(quote_content_start, quote_content_end)
            assert span is not None
            quote_token_count = len(span)
            
            quote_obj = {
                'speaker': person.text,
                'speaker_index': '({0},{1})'.format(person.start_char, person.end_char),
                'quote': quote_content,
                'quote_index': '({0},{1})'.format(quote_content_start, quote_content_end),
                'verb': '',
                'verb_index': '',
                'quote_token_count': quote_token_count,
                'quote_type': 'selon',
                'is_floating_quote': False,
                'reference': person.text
            }
            quote_list.append(quote_obj)
            
        afterSelon = doc.text[person.end_char:q.end(1)]
        stripped, start_index, end_index = stripWithIndices(afterSelon, person.end_char, q.end(1))
        if hasAlpha(stripped):
            quote_content = afterSelon
            quote_content_start = start_index
            quote_content_end = end_index
            
            span = doc.char_span(quote_content_start, quote_content_end)
            assert span is not None
            quote_token_count = len(span)
            
            quote_obj = {
                'speaker': person.text,
                'speaker_index': '({0},{1})'.format(person.start_char, person.end_char),
                'quote': quote_content,
                'quote_index': '({0},{1})'.format(quote_content_start, quote_content_end),
                'verb': '',
                'verb_index': '',
                'quote_token_count': quote_token_count,
                'quote_type': 'QCQVS',
                'is_floating_quote': False,
                'reference': person.text
            }
            quote_list.append(quote_obj)
        
        # Otherwise leave it for the floating quote stage
    
    return quote_list


def extract_one_sided_quotes(doc, quotations):
    
    one_sided_quotes = []
    
    regex_quotes = []
    for match in re.finditer('(?<=")[^"\n]+(?=\n)', doc.text):
#         print(match.group(0))
        
        # ignore quotes that don't start with the right kind of quote char
        if match.start()-1 not in START_GUILLEMETS:
            continue
        
        if not seenBefore(match, quotations):
            regex_quotes.append(match)
    
    # spaCy wrappers
    # Create a dictionary of sentences, sentence numbers, indexed by start character
    sentence_dict = {}
    for i,sent in enumerate(doc.sents):
        sentence_dict[sent.start_char] = i,sent
        
    # Create a dictionary of quotes, indexed by final character
    quotation_dict = {}
    for quotation in quotations:
        indices = []
        for index in ['quote_index', 'verb_index', 'speaker_index']:
            if len(quotation[index]) > 0:
                indices.append(eval(quotation[index])[1])

        quotation_dict[max(indices)] = quotation['speaker']
    
    for q in regex_quotes:
        
        previous_quotation_index = getClosestPreceding(quotation_dict, q.start()-1)
        assert previous_quotation_index < q.start()
        
        if previous_quotation_index != -1:
            candidate_speaker = quotation_dict[previous_quotation_index]
            #print(candidate_speaker)
            
            span = doc.text[previous_quotation_index:q.start()]
            assert span is not None
            #print(previous_quotation_index, q.start())
            
            if not hasAlpha(span):
                span = doc.char_span(q.start()-1, q.end())
                quote_token_count = len(span)

                quote_obj = {
                    'speaker': '',
                    'speaker_index': '',
                    'quote': span.text,
                    'quote_index': '({0},{1})'.format(q.start()-1, q.end()),
                    'verb': '',
                    'verb_index': '',
                    'quote_token_count': quote_token_count,
                    'quote_type': 'QC',
                    'is_floating_quote': True,
                    'reference': candidate_speaker
                }

                one_sided_quotes.append(quote_obj)

    return one_sided_quotes


def get_quote_type(doc, quote, verb, speaker, subtree_span):
    dc1_pos = -1
    dc2_pos = -1
    quote_starts_with_quote = False
    quote_ends_with_quote = False

    if (doc[max(0, quote.start - 1)].is_quote or doc[quote.start].is_quote) and (
            doc[quote.end].is_quote or doc[min(len(doc) - 1, quote.end + 1)].is_quote):
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

    # phrase = subtree_span
    # print('---')
    # print(phrase)
    # print(quote_starts_with_quote, quote_ends_with_quote, " | ", phrase[0].is_quote, phrase[-1].is_quote)
    # print("-> | ", dc1_pos, dc2_pos, content_pos, verb_pos, speaker_pos)
    # print()

    if quote_starts_with_quote and quote_ends_with_quote:
        letters = ["Q", "q", "C", "V", "S"]
        indices = [dc1_pos, dc2_pos, content_pos, verb_pos, speaker_pos]
    else:
        letters = ["C", "V", "S"]
        indices = [content_pos, verb_pos, speaker_pos]

    keydict = dict(zip(letters, indices))
    letters.sort(key=keydict.get)
    return "".join(letters).replace('q', 'Q')


def tokenize_document(spacy_model, doc_id, doc_text, output_dir):
    # Do analysis
    text = preprocess_text(doc_text)
    doc_coref = spacy_model(text)

    last_print_pos = 0
    tokens = []
    words = []

    filename = os.path.join(output_dir, doc_id + '_TOKENIZED.txt')

    tokenized_output_file = open(filename, 'w')

    for word in doc_coref:
        left_idx = word.idx
        right_idx = left_idx + len(str(word))

        token = '({0},{1})'.format(left_idx, right_idx)
        word_str = str(word)

        max_length = max(len(word_str), len(token))
        tokens.append(token.center(max_length))
        words.append(word_str.center(max_length))

        if ((right_idx - last_print_pos) > 100) or len(' '.join(tokens)) > 100:
            tokenized_output_file.writelines(' '.join(words).replace('\n', ' ') + '\n')
            tokenized_output_file.writelines(' '.join(tokens) + '\n')
            tokenized_output_file.writelines('\n\n')

            tokens = []
            words = []
            last_print_pos = right_idx
    if len(tokens) > 0:
        tokenized_output_file.writelines(' '.join(words).replace('\n', ' ') + '\n')
        tokenized_output_file.writelines(' '.join(tokens) + '\n')
        tokenized_output_file.writelines('\n\n')

    tokenized_output_file.close()


if __name__ == '__main__':

    # ========== Important ==========
    # u: username
    # p: password
    # s: server
    # f: force update all
    # ssh-user:
    # ssh-pass:
    # skip-human-readable
    # write-quote-trees-in-file
    write_quote_trees_in_file = False
    update_db = True
    append_human_readable = True
    file_path = None
    folder_path = None
    force_update = False

    DB_NAME = 'mediaTracker'
    COL_NAME = 'media'
    run_on_server = True
    OUTPUT_DIRECTORY = 'output/quote-trees/'
    DOC_LIMIT_COUNT = 0

    MONGO_SERVERS ='localhost'
    MONGO_USER = None
    MONGO_PASS = None
    SSH_USER = None
    SSH_PASS = None
    doc_id = None

    # TODO: shouold write a good man for script
    # sample_command = "quote_extractor.py -u username -p password -s server [-f | --skip-human-readable | write-quote-trees-in-file]"
    sample_command = "Sorry, No sample run is provided yet!"
    try:
        opts, args = getopt.getopt(sys.argv[1:], "hu:p:s:f",
                                   ["db=", "col=", "skip-human-readable", "write-quote-trees-in-file", "dry-run",
                                    "ssh-user=", "ssh-pass=", "file-path=", "folder-path=", "output-dir=", "force-update", "limit=",
                                    "doc-id="])
    except getopt.GetoptError:
        print(sample_command)
        sys.exit(2)

    #  Parse input paremeters
    for opt, arg in opts:
        print("### ", opt, " | ", arg)
        if opt == '-h':
            print(sample_command)
            sys.exit()
        elif opt in ("-u"):
            MONGO_USER = arg
        elif opt in ("-p"):
            MONGO_PASS = arg
        elif opt in ["-s","s"]:
            MONGO_SERVERS = arg
            print('***', arg)
        elif opt in ("--skip-human-readable"):
            append_human_readable = False
        elif opt in ("--write-quote-trees-in-file"):
            write_quote_trees_in_file = True
        elif opt in ("--dry-run"):
            update_db = False
        elif opt in ("ssh-user"):
            run_on_server = False
            SSH_USER = arg
        elif opt in ("ssh-pass"):
            run_on_server = False
            SSH_PASS = arg
        elif opt in ("--file-path"):
            file_path = arg
        elif opt in ("--folder-path"):
            folder_path = arg
        elif opt in ("output-dir"):
            OUTPUT_DIRECTORY = arg
        elif opt in ("--force-update"):
            force_update = True
        elif opt in ("--limit"):
            DOC_LIMIT_COUNT = int(arg)
        elif opt in ("--db"):
            DB_NAME = arg
            print('***', arg)
        elif opt in ("--col"):
            COL_NAME = arg
        elif opt in ("--doc-id"):
            doc_id = arg

    nlp = spacy.load('fr_core_news_md')
    # Create output directory for quote trees if necessary
    if write_quote_trees_in_file and not os.path.exists(OUTPUT_DIRECTORY):
        os.makedirs(OUTPUT_DIRECTORY)
        
    # Parse input files from folder
    if folder_path is not None:
        files = [folder_path+'/'+f for f in os.listdir(folder_path) if f.endswith('.txt')]
        
        for file in files:
            head, file_name = os.path.split(file)
            dot_index = file_name.find('.')
            file_name = file_name[:dot_index]
            
            try:
                doc_text = open(file, 'r').read()
                doc_text = preprocess_text(doc_text)
                doc = nlp(doc_text)
                quotes = extract_quotes(doc_id=file_name, doc=doc, write_tree=write_quote_trees_in_file)

                with open(os.path.join('output/', file_name + '.json'), 'w', encoding='utf-8') as fo:
                    json.dump(quotes, fo, indent=4, ensure_ascii=False)
            except:
                print('EXCEPTION')
                logging.exception("message")
                traceback.print_exc()
        sys.exit(0)
        
    # Parse input file
    if file_path is not None:
        head, file_name = os.path.split(file_path)
        dot_index = file_name.find('.')
        file_name = file_name[:dot_index]
        try:
            doc_text = open(file_path, 'r').read()
            doc_text = preprocess_text(doc_text)
            doc = nlp(doc_text)
            quotes = extract_quotes(doc_id=file_name, doc=doc, write_tree=write_quote_trees_in_file)

            for q in quotes:
                print(q)
                print('-' * 50)
        except:
            print('EXCEPTION')
            logging.exception("message")
            traceback.print_exc()
        sys.exit(0)
    else:  # Parse documents from db
        db_client, server = init(MONGO_SERVERS, MONGO_USER, MONGO_PASS)
        media_tracker_collection = db_client[DB_NAME][COL_NAME]

        query = prepare_query(doc_id, force_update)
        documents = media_tracker_collection.find(query, no_cursor_timeout=True).limit(DOC_LIMIT_COUNT)

        # Run quotation extraction on one document and update db/save quote trees if the parameters are set
        total_documents = documents.count()
        count = 0
        for doc in documents:
            try:
                count = count + 1

                doc_id = str(doc['_id'])
                logging.info('Processing {0:>8}/{1} id: {2}'.format(count, total_documents, doc_id))

                if doc is None:
                    logging.error('Document "{0}" not found.'.format(doc_id))
                else:
                    doc_text = preprocess_text(doc['body'])
                    doc = nlp(doc_text)

                    quotes = extract_quotes(doc_id=doc_id, doc=doc, write_tree=write_quote_trees_in_file)
                    print(update_db)
                    if update_db:
                        media_tracker_collection.update(
                            {
                                '_id': ObjectId(doc_id)
                            },
                            {
                                '$set':
                                    {
                                        'quotes': quotes,
                                        'lastModifier': 'quote_extractor',
                                        'lastModified': datetime.datetime.now()
                                    }
                            }
                        )
                        print('done!')
                    else:
                        print('=' * 20, ' Quotes ', '=' * 20)
                        for q in quotes:
                            print(q,'\n')


            except:
                logging.exception("message")
                traceback.print_exc()

if server is not None:
    server.stop()
