#!flask/bin/python
import json
import logging
import urllib
from urllib.request import urlopen

import requests

import utils
from config import config

logger = utils.create_logger(
    "gender_predictor",
    log_dir="logs",
    logger_level=logging.WARN,
    file_log_level=logging.DEBUG,
)

# Caches
MANUAL_CACHE = config["GENDER_RECOGNITION"]["MANUAL_CACHE"]
GENDERAPI_CACHE = config["GENDER_RECOGNITION"]["GENDERAPI_CACHE"]
GENDERIZE_CACHE = config["GENDER_RECOGNITION"]["GENDERIZE_CACHE"]
FIRSTNAME_CACHE = config["GENDER_RECOGNITION"]["FIRSTNAME_CACHE"]
# Services
GENDERIZE_ENABLED = config["GENDER_RECOGNITION"]["GENDERIZE_ENABLED"]
GENDERAPI_ENABLED = config["GENDER_RECOGNITION"]["GENDERAPI_ENABLED"]
# As of March 2021, we switched to V2 of Gender-API's protocol
# The V2 API uses JSON authentication tokens (and NOT the API key)
# See the unified API docs: https://gender-api.com/en/api-docs/v2
GENDERAPI_TOKEN = config["GENDER_RECOGNITION"]["GENDERAPI_TOKEN"]


class CacheGenderizer:
    """
    Utilize our MongoDB cache, i.e., collections of stored names in our database, to predict gender
    We specify a priority order in terms of quality of each cache, shown below:
        1. Manual cache
        2. Search in GenderAPI cache based on full name (search for {'q': full_name})
        3. Search in Genderize cache for first name
        4. Search in GenderAPI cache based on first name (search for {'name': name})
        5. Search in Firstname cache for first name

    Calling the run() method returns a mapping as follows:
        {"Full Name 1":, "male", "Full Name 2":, "female", ...}
    """

    def __init__(
        self,
        db_client,
        manual_cache_col,
        genderapi_cache_col,
        genderize_cache_col,
        firstname_cache_col,
    ):
        self.manual_cache_col = db_client["genderCache"][manual_cache_col]
        self.genderapi_cache_col = db_client["genderCache"][genderapi_cache_col]
        self.genderize_cache_col = db_client["genderCache"][genderize_cache_col]
        self.firstname_cache_col = db_client["genderCache"][firstname_cache_col]
        # VIAF has been deprecated since early versions due to low accuracy
        # self.viaf_cache_col = db_client["genderCache"][viaf_cache_col]

    def _find_query(self, names, query_field):
        query = {"$or": [{query_field: name} for name in names]}
        return query

    def _update_unknowns(self, results):
        """Return a mapping of only those names that still have 'unknown' as their gender value"""
        unknown_gender_names = {
            name: results[name] for name in results if name and results[name] == "unknown"
        }
        return unknown_gender_names

    def _get_manual_cache_gender(self, names_mapping, query_field="name"):
        lowercased_names = list(names_mapping.keys())
        result = self.manual_cache_col.find(
            self._find_query(lowercased_names, query_field), {"_id": 0}
        )
        result_mapped = dict((names_mapping[item[query_field]], item["gender"]) for item in result)
        return result_mapped

    def _get_genderapi_cache_gender(self, names_mapping, query_field="q"):
        lowercased_names = list(names_mapping.keys())
        result = self.genderapi_cache_col.find(
            self._find_query(lowercased_names, query_field), {"_id": 0}
        )
        result_mapped = dict((names_mapping[item[query_field]], item["gender"]) for item in result)
        return result_mapped

    def _get_genderize_cache_gender(self, names_mapping, query_field="name"):
        lowercased_names = list(names_mapping.keys())
        result = self.genderize_cache_col.find(
            self._find_query(lowercased_names, query_field), {"_id": 0}
        )
        result_mapped = dict((names_mapping[item[query_field]], item["gender"]) for item in result)
        return result_mapped

    def _get_firstname_cache_gender(self, names_mapping, query_field="name"):
        lowercased_names = list(names_mapping.keys())
        result = self.firstname_cache_col.find(
            self._find_query(lowercased_names, query_field), {"_id": 0}
        )
        result_mapped = dict((names_mapping[item[query_field]], item["gender"]) for item in result)
        return result_mapped

    def run(self, names):
        # Define initial results mapping (every gender is unknown at the beginning)
        results = {name: "unknown" for name in names}
        # Obtain a mapping of lowercase, unaccented names to their original form
        names_mapping = {utils.preprocess_text(name).lower(): name for name in names}

        # 1. Try manual cache
        manual_cache_results = self._get_manual_cache_gender(names_mapping, "name")
        results.update(manual_cache_results)  # Update the results with the manual cache results

        # 2. Try GenderAPI based on fullName
        unknowns = self._update_unknowns(results)
        if unknowns:
            names_mapping = {utils.preprocess_text(name).lower(): name for name in unknowns}
            genderapi_cache_fullname_results = self._get_genderapi_cache_gender(names_mapping, "q")
            if genderapi_cache_fullname_results:
                results.update(genderapi_cache_fullname_results)
        else:
            return results, unknowns

        # 3. Try Genderize based on first name
        unknowns = self._update_unknowns(results)
        if unknowns:
            names_mapping = {utils.preprocess_text(name).lower(): name for name in unknowns}
            first_name_mapping = {
                name.split()[0].lower(): name for _, name in names_mapping.items()
            }
            genderize_cache_firstname_results = self._get_genderize_cache_gender(
                first_name_mapping, "name"
            )
            if genderize_cache_firstname_results:
                results.update(genderize_cache_firstname_results)
        else:
            return results, unknowns

        # 4. Try GenderAPI based on first name
        unknowns = self._update_unknowns(results)
        if unknowns:
            names_mapping = {utils.preprocess_text(name).lower(): name for name in unknowns}
            first_name_mapping = {
                name.split()[0].lower(): name for _, name in names_mapping.items()
            }
            genderapi_cache_firstname_results = self._get_genderapi_cache_gender(
                first_name_mapping, "name"
            )
            if genderapi_cache_firstname_results:
                results.update(genderapi_cache_firstname_results)
        else:
            return results, unknowns

        # 5. Try first name cache
        unknowns = self._update_unknowns(results)
        if unknowns:
            names_mapping = {utils.preprocess_text(name).lower(): name for name in unknowns}
            first_name_mapping = {
                name.split()[0].lower(): name for _, name in names_mapping.items()
            }
            firstname_cache_results = self._get_firstname_cache_gender(first_name_mapping, "name")
            if firstname_cache_results:
                results.update(firstname_cache_results)
        else:
            return results, unknowns
        unknowns = self._update_unknowns(results)
        return results, unknowns


# ========== Gender Service functions ==========

def get_viaf_gender(name, db_client, maximum_records=1000):
    """
    DEPRECATED: This function has been deprecated and is no longer in use due to very low accuracy
    It has only been included here for historical records
    """
    viaf_cache_col = db_client["genderCache"]["_VIAF"]
    name = name.strip().lower()
    if " " not in name:
        name = name + " "  # Add space to handle an exception

    female_count = 0
    male_count = 0
    unknown_count = 0
    final_gender = "unknown"

    # Connect to VIAF service
    try:
        some_url = (
            'http://www.viaf.org/viaf/search?query=cql.any+=+"'
            + urllib.parse.quote(name)
            + '"&maximumRecords='
            + str(maximum_records)
            + "&httpAccept=application/json"
        )
        logger.debug('Calling VIAF with: "{0}"'.format(some_url))
        response = urlopen(some_url)

        # Convert bytes to string type and string type to dict
        string = response.read().decode("utf-8")
        json_obj = json.loads(string)
        number_of_records = int(json_obj["searchRetrieveResponse"]["numberOfRecords"])

        if number_of_records > 0:
            records = json_obj["searchRetrieveResponse"]["records"]
            cnt = len(records)
            for i in range(cnt):
                gender = records[i]["record"]["recordData"]["fixed"]["gender"]
                if gender == "a":
                    female_count = female_count + 1
                elif gender == "b":
                    male_count = male_count + 1
                elif gender == "u":
                    unknown_count = unknown_count + 1

            if female_count > male_count:
                final_gender = "female"
            elif male_count > female_count:
                final_gender = "male"
            logger.debug(
                'VIAF service call result for "{0}": "{1}"\t(female:{2}\tmale:{3}\tunknown:{4}\ttotal:{5})'.format(
                    name,
                    final_gender,
                    female_count,
                    male_count,
                    unknown_count,
                    number_of_records,
                )
            )
        gender_cache = {
            "name": name.strip(),
            "gender": final_gender,
            "femaleCount": female_count,
            "maleCount": male_count,
            "unknownCount": unknown_count,
        }
        viaf_cache_col.insert_one(gender_cache)
        return final_gender
    except Exception as e:
        logger.exception("{e}: Failed to obtain gender from VIAF API call".format(e))
        return "unknown"


class ServiceGenderizer:
    def __init__(self, db_client, genderize_cache_col, genderapi_cache_col):
        self.genderize_cache_col = db_client["genderCache"][genderize_cache_col]
        self.genderapi_cache_col = db_client["genderCache"][genderapi_cache_col]

    def get_genderize_gender(self, full_name):
        """Return ONE name's gender per API call"""
        full_name = full_name.lower()
        first_name = utils.extract_first_name(full_name)

        if first_name is None:
            return "unknown"
        else:
            try:
                gender_payload = {"name": first_name}
                # Create a requests session
                session = requests.Session()
                gender_return = session.get("https://api.genderize.io/?", params=gender_payload)
                cache_obj = json.loads(gender_return.text)
                gender = cache_obj["gender"]
                logger.debug(
                    'Genderize service call result for "{0}" ("{1}"): "{2}"'.format(
                        first_name, full_name, gender
                    )
                )
                # Handle unknowns
                if gender is None:
                    gender = "unknown"
                    cache_obj["gender"] = "unknown"
                # Update Genderize cache
                self.genderize_cache_col.insert_one(cache_obj)
                return gender
            except Exception as e:
                logger.exception("{e}: Failed to obtain gender from Genderize API call".format(e))
                return "unknown"

    def get_genderapi_gender(self, session, names):
        """Return multiple full names' genders with ONE Gender-API call"""
        assert all(
            name for name in names
        ), "Empty strings exist in name list, please clean prior to sending for gender prediction"
        results = {}
        try:
            payload = [{"full_name": utils.preprocess_text(name)} for name in names]
            # NOTE: As of March 2021, we switched to V2 of Gender-API's protocol
            # The V2 API uses JSON authentication tokens (and NOT the API key)
            url = "https://gender-api.com/v2/gender"
            headers = {"Authorization": "Bearer {}".format(GENDERAPI_TOKEN)}
            response = session.post(url, headers=headers, json=payload)
            cache_obj = response.json()
            for res in cache_obj:
                full_name = res["input"]["full_name"]
                if res["result_found"]:
                    # Pop unnecessary fields from response JSON prior to storage
                    for field in ["input", "details", "result_found"]:
                        res.pop(field, None)
                    logger.debug(
                        'Obtained GenderAPI service result for "{0}": "{1}"'.format(
                            full_name, res["gender"]
                        )
                    )
                    # Handle unknowns
                    if res["gender"] not in ["male", "female"]:
                        res["gender"] = "unknown"
                    results[full_name] = res["gender"]
                    # Update cache -- 'q' attribute stores the lowercased version of the full name
                    res["q"] = full_name.lower()
                    self.genderapi_cache_col.update_many(
                        {"q": res["q"]}, {"$set": res}, upsert=True
                    )
                else:
                    logger.warning(
                        "No results found for GenderAPI service call for name: {0}".format(
                            full_name
                        )
                    )
                    return results
            return results
        except Exception as e:
            logger.exception("{0}: Failed to obtain gender from Gender-API call".format(e))
            return results

    def run(self, session, results, unknowns):
        """
        Send mappings of {"full_name": "unknown"}, where "unknown" refers to unknown gender,
        to gender services to see if they provide results
        """
        names = list(unknowns.keys())
        if GENDERAPI_ENABLED:
            genderapi_results = self.get_genderapi_gender(session, names)
            results.update(genderapi_results)
        if GENDERIZE_ENABLED:
            for name in names:
                genderize_result = {name: self._get_genderize_gender(name)}
                results.update(genderize_result)
        return results


def get_genders(session, db_client, names):
    assert names, "Empty list passed to the get_genders function"
    # Define initial results mapping (every name's gender is unknown at the beginning)
    unknowns = {name: "unknown" for name in names if not utils.name_length_is_invalid(name)}
    not_processed = {name: "unknown" for name in names if utils.name_length_is_invalid(name)}
    results = unknowns
    cache_genderizer = CacheGenderizer(
        db_client, MANUAL_CACHE, GENDERAPI_CACHE, GENDERIZE_CACHE, FIRSTNAME_CACHE
    )
    results, unknowns = cache_genderizer.run(names)
    if unknowns:
        # Go to external services to try and obtain gender
        service_genderizer = ServiceGenderizer(db_client, GENDERIZE_CACHE, GENDERAPI_CACHE)
        results = service_genderizer.run(session, results, unknowns)

    # Add names that were not processed due to length
    results.update(not_processed)
    return results


if __name__ == "__main__":
    # Test gender prediction on a list of names (requires connection to MongoDB)
    names = [
        "Sheikh Faleh bin Nasser bin Ahmed bin Ali Al Thani",
        "Andres Manuel Lopez Obrador",
        "Ginette Petitpas Taylor",
        "Meng Wanzhou",
        "Bob Corker",
        "Ashley Burke",
    ]

    db_client = utils.init_client(config["MONGO_ARGS"])
    session = requests.Session()
    results = get_genders(session, db_client, names)
    print(results)
