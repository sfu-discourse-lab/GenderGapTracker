# python 3.9

import argparse
import json
import os
import re
from ast import literal_eval

import coreferee
import Levenshtein as lev
import spacy
from spacy.language import Language
from spacy.tokens import Doc, Span, Token

import utils

class FrenchEntityMerger:
    """
    Entity Merger : Link named entities in a doc to the mentions that corefer with them
    nlp : french spacy model compatible with coreferee
    maximum_coreferring_nouns_sentence_referential_distance:
        The sentence range of for coreferring  nouns pairs when building the chains. A
        Higher Number will lead to more complete (longer) chains but with more potential
        errors
    maximum_anaphora_sentence_referential_distance :
        The sentence range for anaphora. Similarly, higher has more coverage but is less
        precise
    """

    gender_titles_dict = {
        "male": [
            "M.",
            "Mm.",
            "Monsieur",
            "Messieurs",
            "Mgr",
            "Monseigneur",
            "président",
        ],
        "female": [
            "Mme",
            "Mmes",
            "Madame",
            "Mesdames",
            "Mlle",
            "Mlles",
            "Mademoiselle",
            "Mesdemoiselles",
            "Vve",
            "Veuve",
            "présidente",
        ],
        "mixed": [
            "Docteur",
            "Dr",
            "Docteurs",
            "Drs",
            "Professeur",
            "Pr",
            "Professeurs",
            "Prs" "Maitre",
            "Maître",
            "Me",
            "ministre",
        ],
    }
    titles_gender_dict = {
        title.lower(): k for k, v in gender_titles_dict.items() for title in v
    }

    titles_regex_dict = {
        t: re.compile(f"\\b{re.escape(t)}(\\b|\s)", re.IGNORECASE)
        for t in titles_gender_dict
    }

    sibling_separator = re.compile("(?:\, )|(?: et )|(?: ou )")

    def __init__(
        self,
        nlp: Language,
        maximum_coreferring_nouns_sentence_referential_distance: int = 3,
        maximum_anaphora_sentence_referential_distance: int = 5,
    ) -> None:

        nlp.get_pipe(
            "coreferee"
        ).annotator.rules_analyzer.maximum_coreferring_nouns_sentence_referential_distance = (
            maximum_coreferring_nouns_sentence_referential_distance
        )
        nlp.get_pipe(
            "coreferee"
        ).annotator.rules_analyzer.maximum_anaphora_sentence_referential_distance = (
            maximum_anaphora_sentence_referential_distance
        )
        self.nlp = nlp
        self.rules_analyzer = nlp.get_pipe("coreferee").annotator.rules_analyzer

    def run(
        self, 
        doc
        ) -> dict[str, tuple[set[tuple[int]], set[str]]]:
        """
        Takes a text document and Produces a dict of entities with:
        key : string representative of entity
        value : set of spans delimiting each heading tokens in each mention of the entity
        """

        ents = self.get_ents(doc)
        coreference_clusters = self.get_coreference_clusters(doc)
        aligned_ents = self.align_clusters_to_ents(coreference_clusters, ents)
        unified_ents = self.unify_ents(coreference_clusters, aligned_ents)
        unified_ents = self.strip_titles(unified_ents)
        return unified_ents

    def clean_ent(self, ent_text: str) -> str:
            ent_text = re.sub("^\W+", "", ent_text)
            ent_text = re.sub("\W+$", "", ent_text)
            return ent_text

    def get_ents(
        self, 
        doc: Doc
        ) -> list[tuple[str, tuple[int, int]]]:
        """
        Get all person named entities in the doc
        and the spans of their heads
        """
        def get_ent_head(ent: Span)-> Token:
            head = ent.root
            #ensures head is not punctuation
            if head.is_punct:
                head_position =  head.i - ent.start
                if head_position == 0 and len(ent) > 1:
                    #punctuation is at beginning of ent
                    head = ent[1:].root
                elif head_position == len(ent) -1:
                    # at end
                    head = ent[:-1].root
                else:
                    # in middle of ent
                    head = ent[:head_position].root
                
            return head
    

        def get_hyphenated_ent(ent: Span) -> Span:
            """
            Spacy has trouble with uncommon hyphenated names due to incorrect tokenisation
            This function checks for hyphens following the end of the entity and
            returns a new extended entity if it finds the entity is not over
            """
            last_token_index = ent.end
            doc = ent.doc
            if (
                last_token_index + 1 <= len(doc) and doc[last_token_index].text == "-"
            ) or (
                last_token_index + 2 <= len(doc)
                and doc[last_token_index + 1].text == "-"
            ):

                last_token_index += 1
                last_token = doc[last_token_index]
                i = 0

                while (
                    last_token.is_alpha
                    and not last_token.is_upper
                    and last_token.text == last_token.text.capitalize()
                ) or (last_token.text == "-" and last_token.whitespace_ == ""):
                    last_token_index += 1
                    if last_token_index >= len(doc):
                        break
                    last_token = doc[last_token_index]
                    i += 1
                    if i > 5:
                        break
                if doc[last_token_index - 1].is_alpha and i > 0:
                    return doc[ent.start : last_token_index]
            return None
        
        def extend_ent(ent: Span) -> Span:
            '''
            Extends ents to include the titles that head them when missing
            '''
            i, j = ent.start, ent.end
            doc = ent.doc
            for i in range(ent.start, 1, -1):
                if not (
                    doc[i].dep_ == "flat:name"
                    and doc[i].head == doc[i - 1]
                    and doc[i - 1].lemma_.lower() in self.titles_gender_dict
                ):
                    break
            for j in range(ent.end, len(doc) - 1):
                if not (doc[j + 1].dep_ == "flat:name" and doc[j + 1].head == doc[j]):
                    break
            return doc[i:j]

        def truncate_ent(ent: Span, ent_head: Token) -> Span:
            '''
            truncates ent that span over punctuations and newlines
            Allows to extract only named entities
            And not their appositions as well as some cleaning
            E.G : Jean Marais, le maire de Gali -> Jean Marais
            '''
            start = ent.start
            end = ent.end
            doc = ent.doc
            for token in ent:
                if (
                    (token.is_punct and token.lemma_ != "-") and
                    not(
                        token.lemma_ == "." and token.i > 0 
                        and len(token.nbor(-1)) < 3 and 
                        not token.nbor(-1).whitespace_
                        )
                    or "\n" in token.text
                ):
                    if token.i < ent_head.i:
                        start = token.i +1
                    if token.i > ent_head.i:
                        end = token.i +1
                        break
            return doc[start:end]

        def strip_adp_phrase(ent: Span, ent_head):
            '''
            Remove prepositional phrases trailing the end
            typically those introduced by "de"
            '''
            doc = ent.doc
            end = ent.end
            prep_de = ["de","des","du","d'"]
            for i in range(ent_head.i+1, ent.end):
                token = doc[i]
                if token.pos_ == "ADP":
                    if token.lower_ not in prep_de:
                        # adps different from "de" (e.g selon) 
                        # must be trimmed in any case
                        end = i
                        break
                    followed_by_last_name = False
                    for j in range(i+1, ent.end):
                        if doc[j].pos_ not in ["PROPN", "X", "DET", "PUNCT"] or\
                             doc[j].lower_ in prep_de:
                            if doc[j].pos_ != "ADP" and doc[j].lower_ not in prep_de:
                                followed_by_last_name = False
                            break
                        # We make the hypothesis that last names
                        # are propn that are 
                        #  neither acronyms nor urls
                        if (
                            doc[j].pos_ == "PROPN"
                            and doc[j].is_title 
                            and not doc[j].is_upper 
                            and not doc[j].like_email
                            and not doc[j].like_url
                        ):
                            followed_by_last_name = True
                    if not followed_by_last_name:
                        end = i
                        break

            return doc[ent.start:end]



        def realign_ent(ent: Span):
            '''
            Wrapper function for all "fixes" done to spacy NEs
            '''
            ent = extend_ent(ent)
            ent_head = get_ent_head(ent) #the root (title) may not be in the original ent
            ent = truncate_ent(ent, ent_head)
            hyphenated_ent = get_hyphenated_ent(ent)
            if hyphenated_ent:
                ent = hyphenated_ent
            ent = strip_adp_phrase(ent, ent_head)
            return ent, ent_head


        entities = []
        for ent in doc.ents:
            if ent.label_ != "PER" :
                continue
            ent , ent_head = realign_ent(ent)
            ent_head_span = (ent.start_char, ent.end_char)
            entities.append((self.clean_ent(ent.text), (ent_head_span,)))

            # Make new ents when there are adjacent coordinated ents
            # "Hugo Dumas et Marie Boucher" -> spacy output the separate two ents
            # Here we add the ent they form together
            siblings = self.rules_analyzer.get_dependent_siblings(ent_head)
            if siblings == []:
                continue
            adjacent_heads_spans = tuple(
                [(t.idx, t.idx + len(t.text)) for t in [ent_head] + siblings]
            )
            extended = False
            for adjacent_ent in doc.ents:
                if adjacent_ent.label_ != "PER":
                    continue

                adjacent_ent, _ = realign_ent(adjacent_ent)
                if siblings[-1] in adjacent_ent:
                    new_ent = doc[ent.start : adjacent_ent.end]
                    if not re.search("[^\w ,\t\-'\.]", new_ent.text):
                        entities.append((self.clean_ent(new_ent.text), adjacent_heads_spans))
                        extended = True
                    break
            if not extended:
                # coordinated not named entities:
                # e . g : Hugos Dumas et ses amis
                last_sibling_phrase_end = list(siblings[-1].subtree)[-1].i
                new_ent = doc[ent.start : last_sibling_phrase_end + 1]
                if not re.search("[^\w ,\t\-'\.]", new_ent.text):
                    entities.append((self.clean_ent(new_ent.text), adjacent_heads_spans))

        return entities

    def get_coreference_clusters(
        self, 
        doc: Doc
        ) -> dict[int, set[tuple[int, int]]]:
        """
        Returns dict of all clusters with
        key : cluster index
        value : set of spans (spans of token heads of each mention)
        """
        coreference_clusters = {}
        for cluster_index, chain in enumerate(doc._.coref_chains):
            coreference_clusters[cluster_index] = set()
            for mention in chain:
                if "Poss=Yes" in doc[mention.root_index].morph:
                    continue
                span_list = utils.get_list_of_spans(mention.token_indexes, doc)
                coreference_clusters[cluster_index].add(tuple(span_list))
        return coreference_clusters

    def align_clusters_to_ents(
        self, 
        clusters: dict[int, set[tuple[int, int]]], 
        ents: list[tuple[str, tuple[int, int]]]
    ) -> dict[tuple[str, tuple[int, int]], int]:
        """
        assigns a cluster number to all the ents
        Browses throughs all mentions and each cluster and looks for
        overlap with the ent spans
        """
        aligned_ents = {}
        for ent in ents:
            _, ent_head_spans = ent
            found_cluster = False
            for cluster_index, cluster in clusters.items():
                for mention_spans in cluster:

                    if utils.has_coverage_for_all(mention_spans, ent_head_spans):
                        if ent in aligned_ents:
                            aligned_ents[ent] += [cluster_index]
                        else:
                            aligned_ents[ent] = [cluster_index]
                        found_cluster = True
                        break
            if not found_cluster:
                # is a singleton
                aligned_ents[ent] = []
        return aligned_ents

    def unify_ents(
        self, 
        clusters: dict[int, set[tuple[int, int]]], 
        aligned_ents:  dict[tuple[str, tuple[int, int]], int]
    ) -> dict[str, tuple[set[tuple[int]], set[str]]]:
        """
        Join the aligned ents and the coreference clusters
        to produce a dictionary of unique entities with the corresponding
        set of spans that refer to them
        """

        def extract_distinctive_names(entity: str) -> tuple:
            """
            Extract potential firsname and lastnames from an entity
            Those will be used in the is_more_representative and can_merge_entities functs
            """
            entity = entity.lower().strip()
            entity_words = entity.split()
            if len(entity_words) == 1:
                first_name = entity
                last_name = entity
                midmost_names = []
            else:
                if entity_words[0] in self.titles_gender_dict:
                    last_name = entity_words[-1]
                    if len(entity_words) > 2:
                        first_name = entity_words[1]
                        midmost_names = entity_words[2:-1]
                    else:
                        first_name = None
                        midmost_names = []
                else:
                    first_name = entity_words[0]
                    last_name = entity_words[-1]
                    midmost_names = entity_words[1:-1]

            return first_name, midmost_names, last_name

        def is_more_representative(entity_text1: str, entity_text2: str) -> bool:
            """
            Checks whether entity1 is more representative than entity2 :
            Presence of a last name is more representative than its absence
            If the two entities have a last name then the presence of a first name is more representative
            Finally if still not decided, the more representative will be the entity with more words
            """
            if utils.are_almost_same(entity_text1.lower(), entity_text2.lower()):
                # First representative has priority as is more likely to
                # have the correct spelling
                return True
            if entity_text2 == "":
                return True
            (
                entity1_first_name,
                entity1_midmost_names,
                entity1_last_name,
            ) = extract_distinctive_names(entity_text1)
            (
                entity2_first_name,
                entity2_midmost_names,
                entity2_last_name,
            ) = extract_distinctive_names(entity_text2)
            if (
                entity1_first_name == entity1_last_name
                and entity2_first_name != entity2_last_name
            ):
                return False
            if (
                entity1_first_name != entity1_last_name
                and entity2_first_name == entity2_last_name
            ):
                #when entity 2 is one token name but entity 1 has at least two tokens
                return True
            if entity1_last_name and not entity2_last_name:
                # When entity 1 has a last name but not entity 2
                return True
            elif entity1_first_name and not entity2_first_name:
                # When they both have a last name but only entity1 has a first name
                return True
            elif entity1_midmost_names and not entity2_midmost_names:
                # Finally we look at middle names / compound last names
                return True

            return len(entity1_midmost_names) > len(entity2_midmost_names)

        def can_merge_entities(
            entity1: tuple[str, set[str]], 
            entity2: tuple[str, set[str]]
            ) -> bool:
            """
            Checks for shared last name and shared first name
            to see if two entities are very likely to corefer and
            and thus their clusters to be merged
            This function is symetric
            """
            def can_merge_parts(entity_a: str, entity_b: str) -> bool:
                for entity_a_part in [p for p in self.sibling_separator.split(entity_a) if p]:
                    mergeable_part = False
                    (
                        entity_a_first_name,
                        entity_a_midmost_names,
                        entity_a_last_name,
                    ) = extract_distinctive_names(entity_a_part)
                    for entity_b_part in [p for p in self.sibling_separator.split(entity_b) if p]:
                        (
                            entity_b_first_name,
                            entity_b_midmost_names,
                            entity_b_last_name,
                        ) = extract_distinctive_names(entity_b_part)
                        # We merge when there is match on last name or first name
                        if (
                            utils.are_almost_same(entity_a_last_name, entity_b_last_name)
                            or utils.are_almost_same(entity_a_first_name, entity_b_first_name)
                            or (entity_a_last_name in entity_b_midmost_names)
                            or (entity_b_last_name in entity_a_midmost_names)
                        ):
                            if (
                                (
                                    entity_a_first_name != entity_a_last_name
                                    and entity_b_first_name != entity_b_last_name
                                )
                                and (
                                    entity_a_first_name is not None
                                    and entity_b_first_name is not None
                                )
                                and (
                                    not utils.are_almost_same(
                                        entity_a_first_name, entity_b_first_name
                                    )
                                )
                            ):
                                # When same last name but different first name (same family)
                                continue
                            if (
                                (
                                    entity_a_first_name != entity_a_last_name
                                    and entity_b_first_name != entity_b_last_name
                                )
                                and (
                                    entity_a_last_name is not None
                                    and entity_b_last_name is not None
                                )
                                and (
                                    not utils.are_almost_same(
                                        entity_a_last_name, entity_b_last_name
                                    )
                                )
                                and (entity_a_last_name not in entity_b_midmost_names)
                                and (entity_b_last_name not in entity_a_midmost_names)
                            ):
                                # When same first name but different last name
                                continue
                            mergeable_part = True
                            break
                    if not mergeable_part:
                        return False
                return True

            entity_text1, titles1 = entity1
            entity_text2, titles2 = entity2
            genders1 = {self.titles_gender_dict[t] for t in titles1} - {"mixed"}
            genders2 = {self.titles_gender_dict[t] for t in titles2} - {"mixed"}
            if len(genders1 | genders2) == 2 and (genders1 ^ genders2):
                # If there is a gender in one of the titles set but not the other
                return False
            return can_merge_parts(entity_text1, entity_text2) and can_merge_parts(
                entity_text2, entity_text1
            )

        def merge_entities_sharing_cluster_index(
            clusters: dict[int, set[tuple[int, int]]], 
            aligned_ents: dict[tuple[str, tuple[int, int]], int]
        ) -> dict[str, tuple[set[tuple[int]], set[str]]]:
            """
            Merge entities that point to the same cluster
            Merge entities with exact same string as well (need to be done here as the string is used as dict key)
            Return a dict  with the entity representative (str) as key and sets of spans as values
            """

            def extract_titles(entity_representative: str) -> set():
                titles = set()
                for title, title_match in self.titles_regex_dict.items():
                    if title_match.search(entity_representative):
                        titles.add(title)
                return titles

            merged_clusters = {}
            for cluster_index in clusters:
                # For each cluster, we look for the most representative entity
                has_ent = False
                representative = ""
                for ent, ent_cluster_index in aligned_ents.items():
                    if cluster_index in ent_cluster_index:
                        has_ent = True
                        ent_text = ent[0]
                        if is_more_representative(ent_text, representative):
                            representative = ent_text
                if has_ent:
                    titles = extract_titles(representative)
                    if representative in merged_clusters:
                        # Merge identical entities
                        merged_clusters[representative][0] |= clusters[cluster_index]
                    else:
                        merged_clusters[representative] = [
                            clusters[cluster_index],
                            titles,
                        ]
            # Adding ent singletons that are not in any clusters
            for ent, ent_cluster_index in aligned_ents.items():
                if ent_cluster_index == []:
                    representative, ent_spans = ent
                    titles = extract_titles(representative)
                    if representative in merged_clusters:
                        merged_clusters[representative][0] |= {ent_spans}
                    else:
                        merged_clusters[representative] = [{ent_spans}, titles]
            return merged_clusters

        merged_clusters = merge_entities_sharing_cluster_index(clusters, aligned_ents)
        for cluster_representative1 in list(merged_clusters.keys()):
            for cluster_representative2 in list(merged_clusters.keys()):
                if cluster_representative1 == cluster_representative2:
                    continue
                # keys may have been already removed during the merging
                if cluster_representative1 not in merged_clusters:
                    continue
                if cluster_representative2 not in merged_clusters:
                    continue

                if can_merge_entities(
                    (
                        cluster_representative1,
                        merged_clusters[cluster_representative1][1],
                    ),
                    (
                        cluster_representative2,
                        merged_clusters[cluster_representative2][1],
                    ),
                ):
                    if is_more_representative(
                        cluster_representative1, cluster_representative2
                    ):
                        spans2, titles2 = merged_clusters.pop(cluster_representative2)
                        merged_clusters[cluster_representative1][0] |= spans2
                        merged_clusters[cluster_representative1][1] |= titles2
                    else:
                        spans1, titles1 = merged_clusters.pop(cluster_representative1)
                        merged_clusters[cluster_representative2][0] |= spans1
                        merged_clusters[cluster_representative2][1] |= titles1

        return merged_clusters

    def strip_titles(
        self, 
        merged_entities: dict[str, tuple[set[tuple[int]], set[str]]]
        ) -> dict[str, tuple[set[tuple[int]], set[str]]]:
        new_merged_entities = {}
        for k, v in merged_entities.items():
            for _, title_match in self.titles_regex_dict.items():
                k = self.clean_ent(title_match.sub("", k))
            new_merged_entities[k] = v
        return new_merged_entities


def extract_noun_phrases(
    unified_ents : dict[str, set],
    doc : Doc,
    rules_analyzer
    ) -> dict[str, set]:
    """
    Get the noun phrases of the mentions :
    Meant for quick visual evaluation
    More processing will be done in quote_merger
    This method can only be run after the run method
    """

    def build_mention(heads, rules_analyzer, detached_dep = None):
        '''Builds a mention span from the heads of a mention
        the mention is built using spacy's french parse tree
        detached_dep : list of dependencies of the head of the mention to exclude from the span
        '''
        doc = heads[0].doc
        mention_pos_before = ("PROPN","NOUN","ADJ","DET","NUM")
        mention_pos_after = ("PROPN","NOUN","ADJ","NUM", "PRON", "PART", "ADV", "VERB", "AUX")
        if detached_dep is None:
            detached_dep = ("appos","dislocated","advmod","obl:mod",
            "obl:arg","obl:agent","obl","orphan","parataxis")
        start = heads[0].left_edge.i
        end = heads[-1].right_edge.i
        siblings = rules_analyzer.get_dependent_siblings(heads[0])
        unincluded_siblings_tokens = set()
        for sibling in siblings:
            if sibling not in heads:
                unincluded_siblings_tokens.update(sibling.subtree)
                unincluded_siblings_tokens.update(doc[sibling.i:end+1])
        #be clauses are parsed differently
        subj_attr_subtree = set()
        cops = [cop for cop in heads[0].children if cop.dep_ == "cop"]
        if cops:
            # We will trim all the tokens that are in the copula or subj attribute
            subjs = [s for s in heads[0].children if s.dep_ == "nsubj"]
            cop_subtree = set(cops[0].subtree)
            subj_subtree = set(subjs[0].subtree) if subjs else set()
            subj_attr_subtree = cop_subtree | subj_subtree
            if cops[0].i < heads[0].i:
                subj_attr_subtree.update(doc[start:cops[0].i])
            if cops[0].i > heads[-1].i:
                subj_attr_subtree.update(doc[cops[0].i:end+1])
            if subjs and subjs[0].i < heads[0].i:
                subj_attr_subtree.update(doc[start:subjs[0].i])
            if subjs and subjs[0].i > heads[-1].i:
                subj_attr_subtree.update(doc[subjs[0].i:end+1])

        detached_tokens = set()
        for c in heads[0].children:
            if (c.dep_ in detached_dep or
            c.dep_ == "acl" and "VerbForm=Inf" in c.morph):
                detached_tokens.update(c.subtree)
                if c.i < heads[0].i:
                    detached_tokens.update(doc[start:c.i])
                if c.i > heads[-1].i:
                    detached_tokens.update(doc[c.i:end+1])
        # Trims the mentions 
        # left
        for i in range(start, heads[0].i, 1):
            if (
                (doc[i].pos_ not in mention_pos_before and doc[i].lemma_ != "-")
                or doc[i] in subj_attr_subtree|detached_tokens|unincluded_siblings_tokens):
                start = i + 1
            else:
                break
        #right
        for j in range(end, heads[-1].i, -1):
            if (
                (doc[j].pos_ not in mention_pos_after )
                or doc[j] in subj_attr_subtree|detached_tokens|unincluded_siblings_tokens):
                end = j - 1
            else:
                break
        return doc[start:end+1]

    new_ents = {}
    for unique_ent in unified_ents:
        new_mentions = set()
        for mention_span in unified_ents[unique_ent][0]:
            heads = tuple(
                [doc.char_span(start, end).root for start, end in mention_span]
            )
            mention = build_mention(heads, rules_analyzer)
            new_mentions.add((heads, mention))

        new_ents[unique_ent] = (new_mentions, tuple(unified_ents[unique_ent][1]))
    return new_ents

def show_entities(noun_phrases_ents):
    print("\nEntities's clusters : \n")
    for entity in noun_phrases_ents:
        print("\n", entity, noun_phrases_ents[entity][1])
        for mention in noun_phrases_ents[entity][0]:
            print(
                "\t",
                "mention heads :",
                mention[0],
                "\t|\t mention phrase :",
                mention[1],
            )


def browse_through_texts(txt_dir, json_dir, nlp):
    """
    Test Function to evaluate results on dummy files
    Will be removed in the final version
    """
    all_pos, all_neg, quotes_nb = 0, 0, 0
    nlp.add_pipe("coreferee")
    analyzer = nlp.get_pipe("coreferee").annotator.rules_analyzer
    entity_merger = FrenchEntityMerger(nlp)
    txt_files = utils.get_files_from_folder(txt_dir, limit=LIMIT)
    for i, doc_name in enumerate(txt_files):
        text = utils.preprocess_text(txt_files[doc_name])
        print("=" * 20, f" {doc_name} : {i} ", "=" * 20)
        json_file = json_dir + doc_name + ".json"
        if not os.path.exists(json_file):
            continue

        quote_objects = json.load(open(json_file, encoding="mac-roman"))
        print("Entities Unification...")
        doc = nlp(utils.preprocess_text(text))
        merged_entities = entity_merger.run(doc)
        # continue
        if VERBOSE:
            noun_phrases_ents = entity_merger.extract_noun_phrases(merged_entities, doc, analyzer)
            show_entities(noun_phrases_ents)

        positives, negatives = compare_outputs(quote_objects, merged_entities, text)
        quotes_nb += len([1 for q in quote_objects if q["speaker_index"]])
        all_pos += positives
        all_neg += negatives

    precision = all_pos / (all_pos + all_neg)
    recall = all_pos / quotes_nb
    # More of a pre evaluation anticipating the next stage (quote merger)
    # As a more suited evaluation of the output of the entity merger would require
    # both annotations that we don't have and more complex coreference evaluation metrics
    print(
        "RESULTS (on speaker's references only) : ",
        f"correct references: {all_pos}",
        f"incorrect references: {all_neg}",
        f"precision: {precision}",
        f"recall: {recall}",
        sep="\n",
    )


def compare_outputs(quote_objects, entities, text):
    pos = neg = 0
    for entity in entities:
        for mention_span in entities[entity][0]:
            start_mention, end_mention = mention_span[0][0], mention_span[-1][-1]
            for quote in quote_objects:
                if not quote["speaker_index"]:
                    continue
                start_speaker, end_speaker = literal_eval(quote["speaker_index"])
                reference = (
                    quote["reference"].replace("’", "'").replace("ÔøΩ", "é").lower()
                )
                if start_speaker <= start_mention <= end_mention <= end_speaker:
                    if entity.lower() == reference:
                        # print("Correct Reference : ",text[start_mention:end_mention], quote["speaker"], entity, quote["reference"], sep= " | " )
                        pos += 1
                    else:
                        print(
                            "Wrong Reference : ",
                            text[start_mention:end_mention],
                            quote["speaker"],
                            entity.lower(),
                            reference,
                            sep=" | ",
                        )
                        neg += 1
    return pos, neg



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Extract unique person entities from doc(s) locally and map them to all their mentions')
    parser.add_argument('--in_dir', type=str,  help="Path to the output directory")
    parser.add_argument('--out_dir', type=str, default= '', help="Path to the output directory")
    parser.add_argument('--target_dir', type=str,  help="Path to the directory containing the json files that is the annotations of the input dir files") 
    parser.add_argument('--spacy_model', type=str, default='fr_core_news_lg', help="spaCy language model to use for NLP and coreferee")
    parser.add_argument('--limit', type=int, default=0, help="Max. number of articles to process")
    parser.add_argument('--verbose', action='store_true',  help="Show merged entities")
    args= parser.parse_args()

    INPUT_DIR = args.in_dir
    TEST_DIR = args.target_dir
    SPACY_MODEL = args.spacy_model
    LIMIT = args.limit
    VERBOSE = args.verbose
    print(f"Loading spaCy language model: {SPACY_MODEL}...")
    NLP = spacy.load(SPACY_MODEL)
    browse_through_texts(INPUT_DIR, TEST_DIR, NLP)
