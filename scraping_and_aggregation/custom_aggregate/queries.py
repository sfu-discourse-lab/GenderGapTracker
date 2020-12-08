"""
This file stores useful database aggregation queries for statistics. The queries take in 
parameters (such as start/end dates) and are returned using method calls as shown below.
"""
from typing import List, Dict, Any
from datetime import timedelta


def db_stats(args: Dict[str, Any]) -> List[object]:
    """Returns the overall counts of articles, quotes, sources, people and
       authors in the database.
    """
    query = [
        {
            "$match": {
                "body": {"$ne": ""},
                "quotesUpdated": {"$exists": True},
                "outlet": {"$in": args['outlets']},
                "publishedAt": {"$gte": args['begin_date'], "$lt": args['end_date'] + timedelta(days=1)}
            }
        },
        {
            "$group": {
                "_id": "null",
                "totalArticles": {"$sum": 1},
                "totalQuotes": {"$sum": "$quoteCount"},
                "peopleFemaleCount": {"$sum": "$peopleFemaleCount"},
                "peopleMaleCount": {"$sum": "$peopleMaleCount"},
                "peopleUnknownCount": {"$sum": "$peopleUnknownCount"},
                "sourcesFemaleCount": {"$sum": "$sourcesFemaleCount"}, 
                "sourcesMaleCount": {"$sum": "$sourcesMaleCount"}, 
                "sourcesUnknownCount": {"$sum": "$sourcesUnknownCount"},
                "authorsFemaleCount": {"$sum": "$authorsFemaleCount"},
                "authorsMaleCount": {"$sum": "$authorsMaleCount"},
                "authorsUnknownCount": {"$sum": "$authorsUnknownCount"}
            }
        }
    ]
    return query


def outlet_stats(args: Dict[str, Any]) -> List[object]:
    """Returns the counts of articles, quotes, sources, people and
       authors grouped by the publishing outlet.
    """
    query = [
        {
            "$match": {
                "body": {"$ne": ""},
                "quotesUpdated": {"$exists": True},
                "outlet": {"$in": args['outlets']},
                "publishedAt": {"$gte": args['begin_date'], "$lt": args['end_date'] + timedelta(days=1)}
            }
        },
        {
            "$group": {
                "_id": "$outlet",
                "totalArticles": {"$sum": 1},
                "totalQuotes": {"$sum": "$quoteCount"},
                "peopleFemaleCount": {"$sum": "$peopleFemaleCount"},
                "peopleMaleCount": {"$sum": "$peopleMaleCount"},
                "peopleUnknownCount": {"$sum": "$peopleUnknownCount"},
                "sourcesFemaleCount": {"$sum": "$sourcesFemaleCount"}, 
                "sourcesMaleCount": {"$sum": "$sourcesMaleCount"}, 
                "sourcesUnknownCount": {"$sum": "$sourcesUnknownCount"},
                "authorsFemaleCount": {"$sum": "$authorsFemaleCount"},
                "authorsMaleCount": {"$sum": "$authorsMaleCount"},
                "authorsUnknownCount": {"$sum": "$authorsUnknownCount"}
            }
        }
    ]
    return query


def top_sources_female(args: Dict[str, Any]) -> List[object]:
    """Returns the names of the top-N female sources (i.e. people quoted).
       If sorted in ascending order, the returned values represent the 
       bottom-N female sources.
    """
    query = [
        { 
            "$match": { 
                "body": {
                    "$ne": ""
                }, 
                "quotesUpdated": { 
                    "$exists": True
                },
                "outlet": {
                    "$in": args['outlets']
                },
                "publishedAt": { 
                    "$gte": args['begin_date'], 
                    "$lt": args['end_date'] + timedelta(days=1)
                }
            }
        }, 
        { 
            "$project": { 
                "outlet": 1.0, 
                "sourcesFemale": 1.0
            }
        }, 
        { 
            "$unwind": { 
                "path": "$sourcesFemale", 
                "preserveNullAndEmptyArrays": False
            }
        }, 
        { 
            "$group": { 
                "_id": "$sourcesFemale", 
                "count": { 
                    "$sum": 1.0
                }
            }
        }, 
        { 
            "$sort": { 
                "count": args['sort']
            }
        }, 
        { 
            "$limit": args['limit']
        }
    ]
    return query


def top_sources_male(args: Dict[str, Any]) -> List[object]:
    """Returns the names of the top-N male sources (i.e. people quoted)
       If sorted in ascending order, the returned values represent the 
       bottom-N male sources.
    """
    query = [
        { 
            "$match": { 
                "body": {
                    "$ne": ""
                }, 
                "quotesUpdated": { 
                    "$exists": True
                },
                "outlet": {
                    "$in": args['outlets']
                },
                "publishedAt": { 
                    "$gte": args['begin_date'], 
                    "$lt": args['end_date'] + timedelta(days=1)
                }
            }
        }, 
        { 
            "$project": { 
                "outlet": 1.0, 
                "sourcesMale": 1.0
            }
        }, 
        { 
            "$unwind": { 
                "path": "$sourcesMale", 
                "preserveNullAndEmptyArrays": False
            }
        }, 
        { 
            "$group": { 
                "_id": "$sourcesMale", 
                "count": { 
                    "$sum": 1.0
                }
            }
        }, 
        { 
            "$sort": { 
                "count": args['sort']
            }
        }, 
        { 
            "$limit": args['limit']
        }
    ]
    return query


def top_sources_unknown(args: Dict[str, Any]) -> List[object]:
    """Returns the names of the top-N unknown sources (i.e. people quoted)
       If sorted in ascending order, the returned values represent the 
       bottom-N unknown sources. This function is useful to identify if the NER
       module is wrongly identifying non-human entities for gender recognition.
    """
    query = [
        { 
            "$match": { 
                "body": {
                    "$ne": ""
                }, 
                "quotesUpdated": { 
                    "$exists": True
                },
                "outlet": {
                    "$in": args['outlets']
                },
                "publishedAt": { 
                    "$gte": args['begin_date'], 
                    "$lt": args['end_date'] + timedelta(days=1)
                }
            }
        }, 
        { 
            "$project": { 
                "outlet": 1.0, 
                "sourcesUnknown": 1.0
            }
        }, 
        { 
            "$unwind": { 
                "path": "$sourcesUnknown", 
                "preserveNullAndEmptyArrays": False
            }
        }, 
        { 
            "$group": { 
                "_id": "$sourcesUnknown", 
                "count": { 
                    "$sum": 1.0
                }
            }
        }, 
        { 
            "$sort": { 
                "count": args['sort']
            }
        }, 
        { 
            "$limit": args['limit']
        }
    ]
    return query


def top_sources_all(args: Dict[str, Any]) -> List[object]:
    """Returns the names of the top-N male + female sources (i.e. people quoted).
       If sorted in ascending order, the returned values represent the 
       bottom-N male + female sources.
    """
    query = [
        { 
            "$match": { 
                "body": {
                    "$ne": ""
                }, 
                "quotesUpdated": { 
                    "$exists": True
                },
                "outlet": {
                    "$in": args['outlets']
                },
                "publishedAt": { 
                    "$gte": args['begin_date'], 
                    "$lt": args['end_date'] + timedelta(days=1)
                }
            }
        }, 
        { 
            "$project": {
                "outlet": 1,
                "sourcesMale": 1,
                "sourcesFemale": 1,
                "allSources": {
                    "$concatArrays": [ 
                        {"$ifNull": ["$sourcesFemale", []]},
                        {"$ifNull": ["$sourcesMale", []]}
                    ]
                }
            }
        }, 
        { 
            "$unwind": { 
                "path": "$allSources", 
                "preserveNullAndEmptyArrays": False
            }
        }, 
        { 
            "$group": { 
                "_id": "$allSources", 
                "count": { 
                    "$sum": 1.0
                }
            }
        }, 
        { 
            "$sort": { 
                "count": args['sort']
            }
        }, 
        { 
            "$limit": args['limit']
        }
    ]
    return query


def female_author_sources(args: Dict[str, Any]) -> List[object]:
    """Returns the total number of male, female and unknown sources for all
       articles written by female authors only, grouped by outlet.
    """
    query = [
        { 
            "$match": { 
                "body": {
                    "$ne": ""
                }, 
                "quotesUpdated": { 
                    "$exists": True
                },
                "outlet": {
                    "$in": args['outlets']
                },
                "publishedAt": { 
                    "$gte": args['begin_date'], 
                    "$lt": args['end_date'] + timedelta(days=1)
                },
                "authorsFemaleCount": {"$gt": 0},
                "authorsMaleCount": 0
            }
        },
        {
            "$project": {    
                "_id": 1,
                "outlet": 1,
                "authors": 1,
                "authorsMale": 1,
                "authorsFemale": 1,
                "authorsUnknown": 1,
                "sourcesMaleCount": 1,
                "sourcesFemaleCount": 1,
                "sourcesUnknownCount": 1
            }
        },
        {
            "$group": {
                "_id": "$outlet",
                "totalArticles": {"$sum": 1},  
                "totalMaleSources": {"$sum": "$sourcesMaleCount"},
                "totalFemaleSources": {"$sum": "$sourcesFemaleCount"},
                "totalUnknownSources": {"$sum": "$sourcesUnknownCount"} 
            }
        },
    ]
    return query


def male_author_sources(args: Dict[str, Any]) -> List[object]:
    """Returns the total number of male, female and unknown sources for all
       articles written by male authors only, grouped by outlet.
    """
    query = [
        { 
            "$match": { 
                "body": {
                    "$ne": ""
                }, 
                "quotesUpdated": { 
                    "$exists": True
                },
                "outlet": {
                    "$in": args['outlets']
                },
                "publishedAt": { 
                    "$gte": args['begin_date'], 
                    "$lt": args['end_date'] + timedelta(days=1)
                },
                "authorsFemaleCount": 0,
                "authorsMaleCount": {"$gt": 0}
            }
        },
        {
            "$project": {    
                "_id": 1,
                "outlet": 1,
                "authors": 1,
                "authorsMale": 1,
                "authorsFemale": 1,
                "authorsUnknown": 1,
                "sourcesMaleCount": 1,
                "sourcesFemaleCount": 1,
                "sourcesUnknownCount": 1
            }
        },
        {
            "$group": {
                "_id": "$outlet",
                "totalArticles": {"$sum": 1},  
                "totalMaleSources": {"$sum": "$sourcesMaleCount"},
                "totalFemaleSources": {"$sum": "$sourcesFemaleCount"},
                "totalUnknownSources": {"$sum": "$sourcesUnknownCount"} 
            }
        },
    ]
    return query


def mixed_author_sources(args: Dict[str, Any]) -> List[object]:
    """Returns the total number of male, female and unknown sources for all
       articles written by male AND female authors, grouped by outlet.
    """
    query = [
        { 
            "$match": { 
                "body": {
                    "$ne": ""
                }, 
                "quotesUpdated": { 
                    "$exists": True
                },
                "outlet": {
                    "$in": args['outlets']
                },
                "publishedAt": { 
                    "$gte": args['begin_date'], 
                    "$lt": args['end_date'] + timedelta(days=1)
                },
                "authorsFemaleCount": {"$gt": 0},
                "authorsMaleCount": {"$gt": 0}
            }
        },
        {
            "$project": {    
                "_id": 1,
                "outlet": 1,
                "authors": 1,
                "authorsMale": 1,
                "authorsFemale": 1,
                "authorsUnknown": 1,
                "sourcesMaleCount": 1,
                "sourcesFemaleCount": 1,
                "sourcesUnknownCount": 1
            }
        },
        {
            "$group": {
                "_id": "$outlet",
                "totalArticles": {"$sum": 1},  
                "totalMaleSources": {"$sum": "$sourcesMaleCount"},
                "totalFemaleSources": {"$sum": "$sourcesFemaleCount"},
                "totalUnknownSources": {"$sum": "$sourcesUnknownCount"} 
            }
        },
    ]
    return query


def unknown_author_sources(args: Dict[str, Any]) -> List[object]:
    """Returns the total number of male, female and unknown sources for all
       articles written by unknown gender authors, grouped by outlet.
    """
    query = [
        { 
            "$match": { 
                "body": {
                    "$ne": ""
                }, 
                "quotesUpdated": { 
                    "$exists": True
                },
                "outlet": {
                    "$in": args['outlets']
                },
                "publishedAt": { 
                    "$gte": args['begin_date'], 
                    "$lt": args['end_date'] + timedelta(days=1)
                },
                "authorsFemaleCount": 0,
                "authorsMaleCount": 0
            }
        },
        {
            "$project": {    
                "_id": 1,
                "outlet": 1,
                "authors": 1,
                "authorsMale": 1,
                "authorsFemale": 1,
                "authorsUnknown": 1,
                "sourcesMaleCount": 1,
                "sourcesFemaleCount": 1,
                "sourcesUnknownCount": 1
            }
        },
        {
            "$group": {
                "_id": "$outlet",
                "totalArticles": {"$sum": 1},  
                "totalMaleSources": {"$sum": "$sourcesMaleCount"},
                "totalFemaleSources": {"$sum": "$sourcesFemaleCount"},
                "totalUnknownSources": {"$sum": "$sourcesUnknownCount"} 
            }
        },
    ]
    return query
