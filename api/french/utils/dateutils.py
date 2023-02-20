from datetime import datetime, timedelta


def is_valid_date_range(start_date: str, end_date: str, lower_bound: str) -> bool:
    tommorrow = datetime.today() + timedelta(days=1)
    if (tommorrow >= convert_date(end_date)) and (
        convert_date(start_date) >= convert_date(lower_bound)
    ):
        return True
    else:
        return False


def convert_date(date_str: str) -> datetime:
    return datetime.strptime(date_str, "%Y-%m-%d")


def get_week_bound(year: int, week: int, day_of_week: int) -> str:
    """
    Get begin or end date for a week of the year as a string YYYY-MM-DD
      - Start of week is Sunday
      - For start of week, set `day_of_week` to 0
      - For end of week, set `day_of_week` to 6
    """
    w_bound = datetime.strptime(f"{year}-{week}-{day_of_week}", "%Y-%U-%w")
    w_bound = w_bound.strftime("%Y-%m-%d")
    return w_bound
