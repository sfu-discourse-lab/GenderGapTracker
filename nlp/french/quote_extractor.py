import argparse
import logging
import traceback
from datetime import datetime, timedelta
from multiprocessing import Pool, cpu_count
import re
import importlib

import spacy
from bson import ObjectId
from spacy.matcher import Matcher
from spacy.tokens import Span

import utils


logger = utils.create_logger(
    "quote_extractor_fr",
    log_dir="logs",
    logger_level=logging.INFO,
    file_log_level=logging.INFO,
)


def chunker(iterable, chunksize):
    """Yield a smaller chunk of a large iterable"""
    for i in range(0, len(iterable), chunksize):
        yield iterable[i : i + chunksize]


def process_chunks(chunk):
    """Pass through a chunk of document IDs and extract quotes"""
    db_client = utils.init_client(MONGO_ARGS)
    collection = db_client[DB_NAME][READ_COL]
    for idx in chunk:
        mongo_doc = collection.find_one({"_id": idx})
        extractor.run(collection, mongo_doc)


def run_pool(poolsize, chunksize):
    """Concurrently perform quote extraction based on a filter query"""
    # Find ALL ids in the database within the query bounds (one-time only)
    client = utils.init_client(MONGO_ARGS)
    id_collection = client[DB_NAME][READ_COL]
    query = utils.prepare_query(filters)
    document_ids = id_collection.find(query).distinct("_id")
    logger.info("Obtained ID list for {} articles.".format(len(document_ids)))

    # Check for doc limit
    if DOC_LIMIT > 0:
        document_ids = document_ids[:DOC_LIMIT]
    logger.info("Processing {} articles...".format(len(document_ids)))

    # Process quotes using a pool of executors
    pool = Pool(processes=poolsize)
    pool.map(process_chunks, chunker(document_ids, chunksize=chunksize))
    pool.close()


class QuoteExtractor:
    config = {}
    nlp = None
    quote_verbs = []
    matchers = {}
    quote_stats = {}

    def __init__(self, config) -> None:
        self.config = config
        self.nlp = config["spacy_lang"]
        self._setup_matchers()
        self._setup_stats()
        self.quote_verbs = [verb for verb in open(config["NLP"]["QUOTE_VERBS"]).read().split()]
        self.out_dir = config["out_dir"] + "/" if config["out_dir"] else ""

    def _setup_matchers(self):
        """Set up spacy regex Matchers to find quotes later on"""
        matchers = {}
        matcher_name = "DIRECT"
        matcher = Matcher(self.nlp.vocab)
        DIRECT_QUOTE_1 = [
            {"TEXT": {"REGEX": ".*(«).*"}},
            {"OP": "+", "TEXT": {"REGEX": "[^«»]"}},
            {"OP": "+", "TEXT": {"REGEX": "[^«»]"}},
            {"TEXT": {"REGEX": ".*(»).*"}},
        ]
        DIRECT_QUOTE_2 = [
            {"TEXT": {"REGEX": ".*(«).*"}},
            {"TEXT": {"REGEX": "[^«»]"}, "OP": "+"},
            {"TEXT": {"REGEX": ".*(«).*"}},
            {"TEXT": {"REGEX": "[^»]"}, "OP": "+"},
            {"TEXT": {"REGEX": ".*(»).*"}},
            {"TEXT": {"REGEX": "[^«»]"}, "OP": "+"},
            {"TEXT": {"REGEX": ".*(»).*"}},
        ]
        matcher.add(matcher_name, [DIRECT_QUOTE_1, DIRECT_QUOTE_2])
        matchers[matcher_name] = matcher

        matcher_name = "SELON"
        matcher = Matcher(self.nlp.vocab)
        SELON_QUOTE = [{"TEXT": {"REGEX": "[Ss]elon$"}}]
        matcher.add(matcher_name, [SELON_QUOTE])
        matchers[matcher_name] = matcher

        self.matchers = matchers

    def _setup_stats(self):
        """Take statistics"""
        quote_stats = {}
        quote_stats["indirect_quotes"] = 0
        quote_stats["direct_quotes"] = 0
        quote_stats["selon_quotes"] = 0
        self.quote_stats = quote_stats

    def _create_quote_obj(
        self,
        speaker_span: Span = None,
        verb_span: Span = None,
        quote_span: Span = None,
        quote_type: str = "",
        is_floating_quote: bool = False,
        reference: str = "",
    ):
        """Create JSON quote object from input"""
        comps = [(quote_span.start, "C")]
        if "«" in quote_span.text:
            comps = [(quote_span.start, "Q")]
            comps.append((quote_span.start + 1, "C"))
        if "»" in quote_span.text:
            comps.append((quote_span.end - 1, "Q"))

        verb_text = ""
        verb_index = ""
        if verb_span:
            comps.append((verb_span.start, "V"))
            verb_text = verb_span.text
            verb_index = str((verb_span.start_char, verb_span.end_char))
        speaker_text = ""
        speaker_index = ""
        if speaker_span:
            comps.append((speaker_span.start, "S"))
            speaker_text = speaker_span.text
            speaker_index = str((speaker_span.start_char, speaker_span.end_char))
        else:
            is_floating_quote = True

        if not quote_type:
            quote_type = "".join(dict(sorted(comps)).values())

        quote_obj = {
            "speaker": speaker_text,
            "speaker_index": speaker_index,
            "quote": quote_span.text,
            "quote_index": str((quote_span.start_char, quote_span.end_char)),
            "verb": verb_text,
            "verb_index": verb_index,
            "quote_token_count": len(quote_span),
            "quote_type": quote_type,
            "is_floating_quote": is_floating_quote,
            "reference": reference,
        }
        return quote_obj

    def _get_matches(self, matcher_name, doc):
        """Given a doc, find all matches using the correct matcher stored in the matcher dict specified in setup().

        Args:
            matcher_name (str): as defined in QuoteExtractor._setup_matchers()
            doc: spacy doc

        Returns:
            (id (int), start (int), end (int)): start, end are token indices
        """
        return self.matchers[matcher_name](doc)

    def _surrounding_quote_sentence_span(self, doc, start, end):
        """Find the surrounding sentence for a direct quote, such that [before]?[quote][after]?

        Args:
            doc (Spacy.doc): .
            start (int): Start index of the quote.
            end (int): End index of the quote.

        Returns:
            before (Spacy.Span | []): Span starting from start of sentence to start of quote.
            quote (Spacy.Span): Quote span.
            after (Spacy.Span | []): Span starting from end of quote to end of sentence.
        """
        sent_start = start
        for i in range(50):
            token = doc[start - i]
            if token.text in [".", "?"]:
                break
            sent_start = token.i
            if token.i == 0:
                break

        sent_end = end - 1
        if not doc[min(end, len(doc) - 1)].text[0].isupper():
            for i in range(min(50, len(doc) - end)):
                token = doc[end + i]
                sent_end = token.i
                if token.text in [".", "?"]:
                    break
        before_span = doc[sent_start:start]
        quote_span = doc[start:end]
        after_span = doc[end : sent_end + 1]
        return before_span, quote_span, after_span

    def _is_not_floating(self, before, after):
        """Ensure that the quote is not floating by searching for word characters in the sentence outside the quotation marks"""
        for c in before.text + after.text:
            if not re.search("[^\w]", c):
                return True
        return False

    def _surrounding_quote_sentence_span_for_indirect(self, doc, start, end):
        """Find the surrounding sentence for a indirect quote.

        Args:
            doc (Spacy.doc): .
            start (int): Start index of the quote.
            end (int): End index of the quote.

        Returns:
            before (Spacy.Span | []): Span starting from start of sentence to start of quote.
            quote (Spacy.Span): Quote span.
            after (Spacy.Span | []): Span starting from end of quote to end of sentence.
        """
        sent_start = start
        for i in range(100):
            token = doc[start - i]
            if token.text in [".", "?"]:
                break
            sent_start = token.i
            if token.i == 0:
                break

        sent_end = end
        if not doc[min(end, len(doc) - 1)].text[0].isupper():
            for i in range(min(100, len(doc) - end)):
                token = doc[end + i]
                sent_end = token.i
                if token.text in [".", "?"]:
                    if token.i < len(doc) - 1 and token.nbor().text == "»":
                        continue
                    break
        return doc[sent_start : sent_end + 1]

    def _verb_candidates_for_direct_quote(self, before: Span, after: Span):
        """returns a generator with candidates ordered by plausibility"""
        first = []
        second = []
        third = []
        if after:
            if not before and "." in after[0].text:
                return
            first += [
                t for t in after if t.text in self.quote_verbs and t.pos_ == "VERB"
            ]
            second += [t for t in after if t.text in self.quote_verbs]
            third += [t for t in after if t.pos_ == "VERB"]
        if before:
            b_list = reversed(list(before))
            first += [
                t for t in b_list if t.text in self.quote_verbs and t.pos_ == "VERB"
            ]
            second += [t for t in b_list if t.text in self.quote_verbs]
        if not after and not before:
            # doesnt happen
            return
        verb_list = first + second + third
        verb_candidates = iter(verb_list)
        return verb_candidates

    def extract_direct_quotes(self, doc, other_quotes):
        """Extract direct quotes from a document.
        Examples include:
        <quote>, dit-elle.
        Il a ajouté que <quote>.

        Args:
            doc (spacy.doc): the doc to extract the quotes from
            other_quotes (List[quote]): list of quotes that have already been extracted from the doc. Used to find the speaker/reference of a floating quote.

        Returns:
            quotes (List[quote]): where each quote is a JSON object
        """
        ents = {ent[0].i: ent for ent in doc.ents if ent.label_ == "PER"}
        quotes = []
        for (
            _,
            start,
            end,
        ) in self._get_matches("DIRECT", doc):
            quote_span = doc[start:end]
            quote = None
            before, quote_span, after = self._surrounding_quote_sentence_span(
                doc, start, end
            )
            sent = doc[before.start : after.end]
            if len(quote_span) < 5:
                continue
            if self._is_not_floating(before, after):
                # if quote is nonfloating direct quote
                verb_candidates = self._verb_candidates_for_direct_quote(before, after)
                if not verb_candidates:
                    continue
                verb = next(verb_candidates, None)
                while verb and verb.dep_ in ["xcomp"] and verb.head.pos_ == "VERB":
                    verb = verb.head
                speaker_list = []
                if verb:
                    if re.search("[Ss]elon", before.text + after.text):
                        continue
                    # add speaker candidates ordered by plausibility
                    speaker_list += [
                        child for child in verb.children if child.dep_ == "nsubj"
                    ]
                    speaker_list += [
                        child
                        for child in verb.children
                        if child.pos_ == "PRON"
                        and child.dep_ in ["dep", "obj", "expl:subj"]
                    ]
                    speaker_list += [
                        child for child in verb.children if child.pos_ == "PROPN"
                    ]
                    speaker_list += [
                        child
                        for child in verb.children
                        if child.pos_ == "NOUN" and child.dep_ == "obj"
                    ]
                    speaker_list += [
                        child
                        for child in after
                        if child.pos_ == "PRON"
                        and child.dep_ in ["dep", "obj", "expl:subj", "flat:name"]
                    ]
                    speaker_list += [
                        child
                        for child in verb.children
                        if child.dep_ == "appos"
                        and child.pos_ in ["NOUN", "PROPN", "PRON"]
                    ]
                    speaker_list += [child for child in after if child.pos_ == "PROPN"]
                    speaker_list += [
                        child
                        for child in doc[verb.i + 1 : sent.end]
                        if child.pos_ == "NOUN"
                    ]
                    speaker_candidates = iter(speaker_list)
                    speaker = next(speaker_candidates, None)
                    speaker_span = None
                    # omit cases such as negations, -t, ca, etc
                    if (
                        speaker
                        and re.search(
                            "(-t|([^\w]|^)ça|([^\w]|^)[Nn](e$|['’]))", speaker.text
                        )
                        and speaker.i < len(doc) - 1
                    ):
                        speaker = (
                            speaker.nbor()
                            if speaker.nbor().pos_ in ["NOUN", "PRON", "PROPN"]
                            else next(speaker_candidates, None)
                        )
                    while speaker and start <= speaker.i <= end:
                        speaker = next(speaker_candidates, None)
                    if speaker:
                        if speaker.i in ents:
                            speaker_span = ents[speaker.i]
                        else:
                            speaker_span = doc[
                                speaker.left_edge.i : speaker.right_edge.i + 1
                            ]
                        verb_span = doc[verb.i : verb.i + 1]
                        quote = self._create_quote_obj(
                            quote_span=quote_span,
                            verb_span=verb_span,
                            speaker_span=speaker_span,
                        )
                        if quote:
                            quotes.append(quote)
                    else:
                        # mostly edge cases
                        continue
                else:
                    # edge cases:
                    # <phrase> : <direct-quote>.
                    colon_phrase = [
                        t
                        for t in doc[quote_span.start - 4 : quote_span.start]
                        if t.text == ":"
                    ]
                    if colon_phrase:
                        speaker_list = []
                        speaker_list += [t for t in sent if t.dep_ == "nsubj"]
                        speaker_list += [
                            t for t in sent if t.pos_ in ["PROPN", "NOUN", "PRON"]
                        ]
                        speaker_list = iter(speaker_list)
                        speaker = next(speaker_list, None)
                        if speaker:
                            speaker_span = doc[
                                speaker.left_edge.i : speaker.right_edge.i + 1
                            ]
                            quote_obj = self._create_quote_obj(
                                reference=speaker_span.text, quote_span=quote_span
                            )
                            quotes.append(quote_obj)
                    continue
            else:
                # is floating quote
                speaker = None
                # cover cases where sent was parsed incorrectly or
                # such as <direct-quote> - Albert Einstein.
                for token in doc[sent.end : sent.end + 4]:
                    if re.search("\w", token.text):
                        break
                    if re.search("(-|–)", token.text):
                        speaker_list = [
                            s
                            for s in doc[token.i + 1 : token.i + 4]
                            if s.pos_ in ["PROPN", "NOUN", "PRON"]
                        ]
                        speaker = next(iter(speaker_list), None)
                        if speaker:
                            speaker_span = doc[
                                speaker.left_edge.i : speaker.right_edge.i + 1
                            ]
                            quote_obj = self._create_quote_obj(
                                reference=speaker_span.text, quote_span=quote_span
                            )
                            quotes.append(quote_obj)
                            break

                if speaker:
                    continue
                verb = None
                # cover the case where «<quote-part-1>, dit-elle. <quote-part-2>»
                for t in quote_span:
                    if t.text == ".":
                        break
                    if t.text in self.quote_verbs:
                        verb = t
                        break
                if verb:
                    # cover the case where «<quote-part-1>, dit-elle. <quote-part-2>»
                    verb_span = doc[verb.i : verb.i + 1]
                    speaker_list = []
                    speaker_list += [t for t in verb.children if t.dep_ == "nsubj"]
                    speaker_list += [
                        t for t in verb.children if t.pos_ in ["PROPN", "NOUN", "PRON"]
                    ]
                    speaker_list = iter(speaker_list)
                    speaker = next(speaker_list, None)
                    # omit cases such as negations, -t, ca, etc
                    if (
                        speaker
                        and re.search(
                            "([-–]t|([^\w]|^)ça|-?[Oo]n([^\w]|$)|([^\w]|^)[Nn](e$|['’]))",
                            speaker.text,
                        )
                        and speaker.i < len(doc) - 1
                    ):
                        speaker = next(speaker_list, None)
                    if speaker:
                        speaker_span = doc[
                            speaker.left_edge.i : speaker.right_edge.i + 1
                        ]
                        part1_quote_span = doc[quote_span.start : verb.i]
                        quote_obj = self._create_quote_obj(
                            speaker_span=speaker_span,
                            quote_span=part1_quote_span,
                            verb_span=verb_span,
                        )
                        quotes.append(quote_obj)
                        part2_quote_span = doc[verb.sent.end : quote_span.end]
                        if part2_quote_span:
                            quote_obj = self._create_quote_obj(
                                speaker_span=speaker_span, quote_span=part2_quote_span
                            )
                            quotes.append(quote_obj)
                        continue
                reference = None

                # Find the last quoted speaker/reference
                # sort quotes by start quote index
                all_quotes = sorted(
                    other_quotes + quotes, key=lambda d: eval(d["quote_index"])[1]
                )
                for quote in reversed(all_quotes):
                    if eval(quote["quote_index"])[1] < doc[quote_span.start].idx:
                        reference = None
                        if "reference" in quote and quote["reference"]:
                            reference = quote["reference"]
                        elif "speaker" in quote and quote["speaker"]:
                            reference = quote["speaker"]
                        if reference and re.search("[-–]?([Ee]lle|[Ii]l)$", reference):
                            continue
                        elif reference:
                            break
                if reference:
                    quote_obj = self._create_quote_obj(
                        reference=reference, quote_span=quote_span
                    )
                    quotes.append(quote_obj)
                continue
        return quotes

    def extract_indirect_quotes(self, doc):
        """Extract all indirect quotes from a document

        Args:
            doc: doc to extract from

        Returns:
            quotes (List[quote]): where quote is a JSON quote object
        """
        quote_list = []
        direct_matches = self._get_matches("DIRECT", doc)
        for word in doc:
            verb = None
            speaker = None
            verb_span = None
            quote_span = None
            speaker_span = None
            speaker_list = []
            if word.text in self.quote_verbs:
                # get the full sentence in which the quote appears
                sent = self._surrounding_quote_sentence_span_for_indirect(
                    doc, word.sent.start, word.sent.end - 1
                )
                while sent[0].pos_ == "SPACE":
                    sent = doc[sent.start + 1 : sent.end]
                while sent[-1].pos_ == "SPACE":
                    sent = doc[sent.start : sent.end - 1]
                # if it is a direct quote
                if re.search("«[^»]{20,}", sent.text):
                    continue
                if re.search("[^«]{20,}»", sent.text):
                    continue
                if re.search("[!?.]»", sent.text):
                    continue
                # omit phrases containing selon to avoid duplicates
                if re.search("(([^\w]|^)[Ss]elon([^\w]|$))", sent.text):
                    continue
                # omit if this is an indrect quotes contained in a direct quote
                if [
                    1 for (a, start, end) in direct_matches if start <= sent.start < end
                ]:
                    continue
                # omit "il faut"
                if (
                    (1 < word.i < len(doc)-1)
                    and re.search("([^\w]|^)[Ii]l$", word.nbor(-2).text)
                    and word.nbor(-1).text == "faut"
                ):
                    continue
                # omit negated verbs
                if re.search("([^\w]|^)[Nn](e |['’])", doc[word.i - 3 : word.i].text):
                    continue
                # often incorrectly tagged verbs
                if word.pos_ != "VERB":
                    if word.text in ["demande"]:
                        continue
                comp_list = [token for token in word.children if "comp" in token.dep_]
                comp = next(iter(comp_list), None)
                hyph_pron_list = [
                    t for t in doc[word.i - 3 : word.i] if t.text in ["-elle", "-il"]
                ]
                hyph_pron = next(iter(hyph_pron_list), None)
                # cover the case were: <quote>, ajoute-elle.
                if hyph_pron:
                    verb = word
                    quote_span = doc[sent.start : hyph_pron.i - 1]
                    speaker = hyph_pron
                # cover the classic case: elle dit que <quote>.
                elif re.search(
                    "([^\w]|^| )qu(['’]|e($| ))", doc[word.i : word.i + 7].text
                ):
                    verb = word
                    quote_span = doc[verb.i + 1 : verb.right_edge.i]
                    speaker_list += [
                        child
                        for child in doc[sent.start : verb.i]
                        if child.dep_ == "nsubj"
                    ]
                    speaker_list += [
                        child
                        for child in doc[sent.start : verb.i]
                        if child.pos_ == "PRON"
                        and child.dep_ in ["dep", "obj", "expl:subj"]
                    ]
                    speaker_list += [
                        child
                        for child in doc[sent.start : verb.i]
                        if child.pos_ == "PROPN" and child.dep_ in ["flat:name"]
                    ]
                    speaker_list += [
                        child
                        for child in doc[sent.start : verb.i]
                        if child.pos_ == "NOUN" and child.dep_ == "obj"
                    ]
                    speaker_list += [
                        child
                        for child in doc[sent.start : verb.i]
                        if child.pos_ == "PROPN"
                    ]
                    candidates = iter(speaker_list)
                    speaker = next(candidates, None)
                    pass
                # cover cases such as: elle ajoute des <quote>
                elif re.search("(^| )des4($| )", doc[word.i + 1 : word.i + 2].text):
                    verb = word
                    quote_span = doc[verb.i + 1 : sent.end]
                    pass
                # cover cases such as: elle ajoute de <quote>
                elif re.search(
                    "(^| )d(['’]|e($| ))", doc[word.i + 1 : word.i + 3].text
                ):
                    if re.search("é$", word.text):
                        continue
                    verb = word
                    quote_span = doc[verb.i + 1 : sent.end]
                    pass
                # cover cases such as: <quote>, note le ministre.
                elif (0 < word.i < len(doc) - 1) and re.search(",", word.nbor(-1).text):
                    if re.search("^(par|à)$", word.nbor().text):
                        continue
                    verb = word
                    # add speaker candidates by plausibility
                    quote_span = doc[sent.start : verb.i]
                    speaker_list += [
                        child
                        for child in doc[verb.i - 2 : sent.end]
                        if child.dep_ == "nsubj"
                    ]
                    speaker_list += [
                        child
                        for child in doc[verb.i - 2 : sent.end]
                        if child.pos_ == "PRON"
                        and child.dep_ in ["dep", "obj", "expl:subj"]
                    ]
                    speaker_list += [
                        child
                        for child in doc[verb.i - 2 : sent.end]
                        if child.pos_ == "PROPN" and child.dep_ in ["flat:name"]
                    ]
                    speaker_list += [
                        child
                        for child in doc[verb.i - 2 : sent.end]
                        if child.pos_ == "NOUN" and child.dep_ == "obj"
                    ]
                    speaker_list += [
                        child
                        for child in doc[verb.i - 2 : sent.end]
                        if child.pos_ == "PROPN"
                    ]
                    candidates = iter(speaker_list)
                    speaker = next(candidates, None)
                    pass
                elif comp:
                    # cover ccomp cases that have not been covered in other cases
                    if comp.dep_ == "ccomp":
                        if comp.pos_ == "VERB":
                            verb = word
                            quote_span = doc[verb.i + 1 : sent.end]
                    # cover xcomp cases that have not been covered in other cases, including some special cases
                    elif comp.dep_ == "xcomp":
                        if word.text in ["dit"]:
                            verb = word
                            quote_span = doc[verb.i + 1 : sent.end]
                        elif comp.text in ["avoir"]:
                            verb = word
                            quote_span = doc[verb.i + 1 : sent.end]
                elif re.search(", (a|ont)( |$)", doc[word.i - 3 : word.i].text):
                    # cover the case such as: <quote>, a dit la fille.
                    verb = word
                    quote_span = doc[sent.start : verb.i]
                    speaker_list += [
                        child
                        for child in doc[verb.i - 2 : sent.end]
                        if child.dep_ == "nsubj"
                    ]
                    speaker_list += [
                        child
                        for child in doc[verb.i - 2 : sent.end]
                        if child.pos_ == "PRON"
                        and child.dep_ in ["dep", "obj", "expl:subj"]
                    ]
                    speaker_list += [
                        child
                        for child in doc[verb.i - 2 : sent.end]
                        if child.pos_ == "PROPN" and child.dep_ in ["flat:name"]
                    ]
                    speaker_list += [
                        child
                        for child in doc[verb.i - 2 : sent.end]
                        if child.pos_ == "NOUN" and child.dep_ == "obj"
                    ]
                    speaker_list += [
                        child
                        for child in doc[verb.i - 2 : sent.end]
                        if child.pos_ == "PROPN"
                    ]
                    candidates = iter(speaker_list)
                    speaker = next(candidates, None)
                    pass
                elif word.pos_ == "VERB":
                    # cover special cases
                    if word.text in ["annonce", "ordonne", "reproche"]:
                        verb = word
                        quote_span = doc[verb.i + 1 : sent.end]
                else:
                    continue

                if quote_span:
                    if len(quote_span) < 5:
                        continue
                    if verb:
                        verb_span = doc[verb.i : verb.i + 1]
                    if not speaker:
                        if word.text.endswith("ant"):
                            # verbs ending with -ant reuiqre a different speaker heuristic:
                            speaker_list += [
                                child for child in sent if child.dep_ == "nsubj"
                            ]
                            speaker_list += [
                                child
                                for child in sent
                                if child.pos_ == "PRON"
                                and child.dep_ in ["dep", "obj", "expl:subj"]
                            ]
                            speaker_list += [
                                child
                                for child in sent
                                if child.pos_ == "PROPN" and child.dep_ in ["flat:name"]
                            ]
                            speaker_list += [
                                child for child in sent if child.pos_ == "PROPN"
                            ]
                        speaker_list += [
                            child for child in verb.children if child.dep_ == "nsubj"
                        ]
                        speaker_list += [
                            child
                            for child in verb.children
                            if child.pos_ == "PRON"
                            and child.dep_ in ["dep", "obj", "expl:subj"]
                        ]
                        speaker_list += [
                            child
                            for child in verb.children
                            if child.pos_ == "PROPN" and child.dep_ in ["flat:name"]
                        ]
                        speaker_list += [
                            child
                            for child in verb.children
                            if child.pos_ == "NOUN" and child.dep_ == "obj"
                        ]
                        speaker_list += [
                            child for child in verb.children if child.pos_ == "PROPN"
                        ]
                        candidates = iter(speaker_list)
                        speaker = next(candidates, None)
                    # omit speaker candidates that are in the quote span.
                    while speaker and quote_span.start <= speaker.i < quote_span.end:
                        speaker = next(candidates, None)
                    if speaker:
                        speaker_span = doc[
                            speaker.left_edge.i : speaker.right_edge.i + 1
                        ]
                        quote_obj = self._create_quote_obj(
                            quote_span=quote_span,
                            verb_span=verb_span,
                            speaker_span=speaker_span,
                        )
                        if quote_obj:
                            quote_list.append(quote_obj)
        return quote_list

    def extract_selon_quotes(self, doc):
        """Extract quotes from a doc that are initiated by "selon".
        Examples include:
        Selon la fille, <quote>
        <quote>, selon le garçon.

        Args:
            doc (spacy.doc): .

        Returns:
            quotes (List[quote]): List of quotes where each quote is a JSON object.
        """
        quotes = []
        for (
            _,
            start,
            end,
        ) in self._get_matches("SELON", doc):
            if doc[end].tag_ not in ["NOUN", "PROPN", "DET", "PRON"]:
                continue
            speaker = doc[start].head
            speaker_span = doc[end : speaker.right_edge.i + 1]
            if speaker.head.i > speaker.i:
                quote_span = doc[speaker.right_edge.i + 1 : speaker.sent.end + 1]
            else:
                quote_span = doc[speaker_span.sent.start : start]
            if speaker_span:
                # avoid common false positives
                if re.search("([Ll]|[Mm])oi[,. ]?$", speaker_span.text):
                    continue
                if len(quote_span) < 4:
                    continue
                quote_obj = self._create_quote_obj(
                    speaker_span=speaker_span,
                    verb_span=None,
                    quote_span=quote_span,
                    quote_type="selon",
                )
                if quote_obj:
                    quotes.append(quote_obj)
        return quotes

    def extract_quotes(self, doc):
        """Extract quotes from a given doc using the different extraction mechanisms and/or quote types.

        Args:
            doc (spacy.doc): Spacy Document which all quotes should be extracted from.

        Returns:
            quotes (List[quote]): List of quotes where each quote is a JSON object.
        """
        quotes = []
        indirect_quotes = self.extract_indirect_quotes(doc)
        quotes += indirect_quotes
        selon_quotes = self.extract_selon_quotes(doc)
        quotes += selon_quotes
        direct_quotes = self.extract_direct_quotes(doc, quotes)
        quotes += direct_quotes

        self.quote_stats["indirect_quotes"] += len(indirect_quotes)
        self.quote_stats["direct_quotes"] += len(direct_quotes)
        self.quote_stats["selon_quotes"] += len(selon_quotes)

        return quotes

    def run(self, collection, mongo_doc):
        """Run quote extraction on a MongoDB document, and write quotes to a specified collection in the database"""
        
        try:
            doc_id = str(mongo_doc["_id"])
            if mongo_doc is None:
                logger.error('Document "{0}" not found.'.format(doc_id))
            else:
                text = mongo_doc["body"]
                text_length = len(text)
                if text_length > self.config["NLP"]["MAX_BODY_LENGTH"]:
                    logger.warning(
                        "Skipping document {0} due to long length {1} characters".format(
                            mongo_doc["_id"], text_length
                        )
                    )
                    if not self.config["dry_run"]:
                        collection.update_one(
                            {"_id": ObjectId(doc_id)},
                            {
                                "$set": {
                                    "lastModifier": "max_body_len",
                                    "lastModified": datetime.now(),
                                },
                                "$unset": {"quotes": 1},
                            },
                            upsert=True,
                        )
                # Process document
                doc_text = utils.preprocess_text(mongo_doc["body"])
                spacy_doc = self.nlp(doc_text)
                quotes = self.extract_quotes(spacy_doc)

                if not self.config["dry_run"]:
                    collection.update_one(
                        {"_id": ObjectId(doc_id)},
                        {
                            "$set": {
                                "quotes": quotes,
                                "lastModifier": "quote_extractor_fr",
                                "lastModified": datetime.now(),
                            }
                        },
                    )
                else:
                    # If dry run, then display extracted quotes (for testing)
                    print("=" * 20, f" {doc_id} ", "=" * 20)
                    if not self.out_dir:
                        for q in quotes[:]:
                            print(
                                f"""\nSPEAKER:   {repr(q["speaker"])}\n   VERB:   {repr(q["verb"])}\n  QUOTE:   {repr(q["quote"])}\n"""
                            )
                    return quotes
        except:
            logger.exception(f"Failed to process {mongo_doc['_id']} due to runtime exception!")
            traceback.print_exc()

    def print_stats(self):
        sumall = sum(self.quote_stats.values())
        for quote_type, value in self.quote_stats.items():
            if sumall > 0:
                print(f"{quote_type}: {100*value/sumall:.4}% ({value}/{sumall})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract quotes from doc(s) locally or push to db.")
    parser.add_argument("--config_file", type=str, default="config", help="Name of config file")
    parser.add_argument("--db", type=str, default="mediaTracker", help="Database name")
    parser.add_argument("--readcol", type=str, default="media", help="Collection name")
    parser.add_argument("--dry_run", action="store_true", help="Do not write anything to database (dry run)")
    parser.add_argument("--force_update", action="store_true", help="Overwrite already processed documents in database")
    parser.add_argument("--in_dir", type=str, default="", help="Path to read input text files from this directory.")
    parser.add_argument("--out_dir", type=str, default="", help="Path to write JSON quotes to this directory.")
    parser.add_argument("--limit", type=int, default=0, help="Max. number of articles to process")
    parser.add_argument("--begin_date", type=str, help="Start date of articles to process (YYYY-MM-DD)")
    parser.add_argument("--end_date", type=str, help="End date of articles to process (YYYY-MM-DD)")
    parser.add_argument("--outlets", type=str, help="Comma-separated list of news outlets to consider in query scope")
    parser.add_argument("--ids", type=str, help="Comma-separated list of document ids to process. \
                                               By default, all documents in the collection are processed.")
    parser.add_argument("--spacy_model", type=str, default="fr_core_news_lg", help="spaCy language model to use for NLP")
    parser.add_argument("--poolsize", type=int, default=cpu_count(), help="Size of the concurrent process pool for the given task")
    parser.add_argument("--chunksize", type=int, default=20, help="Number of articles IDs per chunk being processed concurrently")

    dargs = parser.parse_args()
    args = vars(dargs)

    # ========== Parse config params and arguments ==========
    config_file_name = args["config_file"]
    config_file = importlib.import_module(config_file_name)
    config = config_file.config

    MONGO_ARGS = config["MONGO_ARGS"]

    DB_NAME = args["db"]
    READ_COL = args["readcol"]
    DOC_LIMIT = args["limit"]
    UPDATE_DB = not args["dry_run"]  # Do not update db when we request a dry run
    FORCE_UPDATE = args["force_update"]
    IN_DIR = args["in_dir"] + "/" if args["in_dir"] else ""
    OUT_DIR = args["out_dir"] + "/" if args["out_dir"] else ""
    POOLSIZE = args["poolsize"]
    CHUNKSIZE = args["chunksize"]

    date_begin = utils.convert_date(args["begin_date"]) if args["begin_date"] else None
    date_end = utils.convert_date(args["end_date"]) if args["begin_date"] else None

    date_filters = []
    if date_begin:
        date_filters.append({"publishedAt": {"$gte": date_begin}})
    if date_end:
        date_filters.append({"publishedAt": {"$lt": date_end + timedelta(days=1)}})

    if FORCE_UPDATE:
        other_filters = []
    else:
        other_filters = [
            {"quotes": {"$exists": False}},
            {"lastModifier": "mediaCollectors"},
        ]

    doc_id_list = args["ids"] if args["ids"] else None
    outlet_list = args["outlets"] if args["outlets"] else None

    filters = {
        "doc_id_list": doc_id_list,
        "outlets": outlet_list,
        "force_update": FORCE_UPDATE,
        "date_filters": date_filters,
        "other_filters": other_filters,
    }

    print(f"Loading spaCy language model: {args['spacy_model']}...")
    nlp = spacy.load(args["spacy_model"])
    args["spacy_lang"] = nlp
    config |= args
    print("Finished loading")

    extractor = QuoteExtractor(config)
    db_client = utils.init_client(MONGO_ARGS)
    query = utils.prepare_query(filters)

    if IN_DIR:
        UPDATE_DB = False
        # Add custom read/write logic for local machine here
        file_dict = utils.get_files_from_folder(folder_path=IN_DIR, limit=DOC_LIMIT)
        for idx, text in file_dict.items():
            doc = {"_id": idx, "body": text}
            doc_quotes = extractor.run(collection=None, mongo_doc=doc)
            quote_dict = {idx: doc_quotes}
            if OUT_DIR:
                utils.write_quotes_local(quote_dict=quote_dict, output_dir=OUT_DIR)
        print(f'Retrieveved {len(file_dict)} files from "{IN_DIR}"')

    else:
        # Directly parse documents from the db, and write back to db
        run_pool(poolsize=POOLSIZE, chunksize=CHUNKSIZE)
        logger.info("Finished processing quotes.")
