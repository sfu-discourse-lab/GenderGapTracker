from datetime import datetime

def agg_total_per_outlet(begin_date: datetime, end_date: datetime):
    query = [
        {"$match": {"publishedAt": {"$gte": begin_date, "$lte": end_date}}},
        {
            "$group": {
                "_id": "$outlet",
                "totalArticles": {"$sum": "$totalArticles"},
                "totalFemales": {"$sum": "$totalFemales"},
                "totalMales": {"$sum": "$totalMales"},
                "totalUnknowns": {"$sum": "$totalUnknowns"},
            }
        },
    ]
    return query


def agg_total_by_week(begin_date: datetime, end_date: datetime):
    query = [
        {"$match": {"publishedAt": {"$gte": begin_date, "$lte": end_date}}},
        {
            "$group": {
                "_id": {
                    "outlet": "$outlet",
                    "week": {"$week": "$publishedAt"},
                    "year": {"$year": "$publishedAt"},
                },
                "totalFemales": {"$sum": "$totalFemales"},
                "totalMales": {"$sum": "$totalMales"},
                "totalUnknowns": {"$sum": "$totalUnknowns"},
            }
        },
    ]
    return query
