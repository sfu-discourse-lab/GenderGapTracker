#!flask/bin/python
import json
import logging
import urllib
from bson import ObjectId
from urllib.request import urlopen, quote

import requests
from flask import Flask, request, jsonify
from config import config
import utils

app = Flask(__name__)

gender_logger = utils.create_logger('gender_recognition', log_dir='logs', logger_level=logging.WARN,
                                    file_log_level=logging.DEBUG)

db_client = utils.init_client(config['MONGO_ARGS'])

viaf_cache_col = db_client['genderCache']['VIAF']
genderapi_cache_col = db_client['genderCache']['genderAPICleaned']
genderize_cache_col = db_client['genderCache']['genderizeCleaned']
firstname_cache_col = db_client['genderCache']['firstNamesCleaned']
manual_cache_col = db_client['genderCache']['manual']

GENDERIZE_ENABLED = config['GENDER_RECOGNITION']['GENDERIZE_ENABLED']
GENDERAPI_ENABLED = config['GENDER_RECOGNITION']['GENDERAPI_ENABLED']
GENDER_PORT = config['GENDER_RECOGNITION']['PORT']
GENDERAPI_TOKEN = config['GENDER_RECOGNITION']['GENDERAPI_TOKEN']


@app.route('/get-genders')
def get_genders():
    people = request.args.get('people', type=str)
    people = people.split(',')

    disable_cache = request.args.get('disable_cache', default=False, type=bool)
    disable_service = request.args.get('disable_service', default=False, type=bool)

    people_genders = {}
    for person in people:
        gender, _, _ = get_gender(person, disable_cache, disable_service)
        people_genders[person] = gender
    json_res = jsonify(people_genders)
    return json_res


@app.route('/get-gender')
def get_gender_service():
    name = request.args.get('name', type=str)
    if name is None:
        raise ValueError('name is not provided.')

    print(utils.extract_first_name(name))

    disable_cache = request.args.get('disable_cache', default=False, type=bool)
    disable_service = request.args.get('disable_service', default=False, type=bool)
    gender, gender_source, cached = get_gender(name, disable_cache, disable_service)

    return jsonify({'gender': gender, 'gender_source': gender_source, 'cached': cached, 'successful': True})


def get_gender(name, disable_cache=False, disable_service=False):
    name = utils.clean_ne(name)

    # ===== Checking for trivial cases =====
    # (len(name.split(" ")) > 5 is added to not resolve gender for long texts!
    # Length of 5 is chosen because Arabic names are commonly 5 words long.
    if (len(name.split(" ")) <= 1) or (len(name.split(" ")) > 5):
        gender_logger.warning('Skipping gender assignment due name length: "{0}"'.format(name))
        return 'unknown', 'Hardcode', True
    # Check he/shes manually
    if name.lower() == 'he':
        return 'male', 'Hardcode', True
    if name.lower() == 'she':
        return 'female', 'Hardcode', True
    # Check editorial case
    if 'editorial' in name.lower():
        return 'editorial', 'Hardcode', True

    # Checking cache for given name
    if not disable_cache:
        gender_logger.info('Checking cache for "{0}"'.format(name))
        gender, cache_name, ignore_list = get_gender_from_cache(name)

        if cache_name == 'Manual' or gender != 'unknown':
            gender_logger.info('"{0}" cache identified gender for "{1}:{2}"'.format(cache_name, name, gender))
            return gender, cache_name, True
    else:
        ignore_list = []

    # Checking Service for given name

    if not disable_service:
        gender_logger.info('Cache missed gender for "{0}". Calling services to identify gender.'.format(name))
        gender, service_name = get_gender_from_service(name, ignore_list)
        gender_logger.info('Services result for "{0}" is "{1}" with "{2}"'.format(name, gender, service_name))

        # Update FirstName Cache if applicable (ony using first name based services)
        first_name = utils.extract_first_name(name.lower())
        if gender in ['male', 'female'] and first_name is not None and service_name not in ['VIAF']:
            existing_item = firstname_cache_col.find_one({'name': first_name})
            if existing_item is None:
                firstname_cache_col.insert_one({'name': first_name, 'gender': gender})
            else:
                curr_name_id = existing_item['_id']
                if existing_item['gender'] is None or existing_item['gender'] == 'unknown':
                    firstname_cache_col.update({'_id': ObjectId(curr_name_id)}, {'$set': {'gender': gender}})
                    gender_logger.info(
                        'Update Cache "{0}" as first name for "{1}" as "{2}"'.format(first_name, name, gender))

                elif existing_item['gender'] != gender:
                    gender_logger.warning(
                        'Gender Mismatch for "{0}": FirstName Cache: "{1}"   {2}: "{3}"'.format(first_name,
                                                                                                existing_item['gender'],
                                                                                                service_name, gender))

        # Return result
        if gender is None or gender == 'unknown':
            gender_logger.warning('Unable to identify gender for "{0}"'.format(name))

        return gender, service_name, False

    return 'unknown', 'unknown', False


# ========== Gender functions ==========

# The priorities to get gender from cache:
# 1. Manual cache
# 2. GenderAPI_FullName: GenderAPI based on split API (full name). search for {'q': full_name}
# 3. Search in Genderize cache for first name (if first name is detected)
# 4. Search in GenderAPI_Firstname cache for first name (if first name is detected)
# 5. Search in Firstname cache for first name (if first name is detected)

def get_gender_from_cache(full_name):
    full_name = utils.clean_ne(full_name).lower()
    first_name = utils.extract_first_name(full_name)
    log_stmt_format = '"{0}" cache result for First Name: "{1}" | Full Name: "{2}"\t: "{3}"'
    ignore_list = []

    # ========== Checking Manual cache ==========
    # Check the manual cache with highest priority
    service_name = 'Manual'
    existing_gender = manual_cache_col.find_one({'name': full_name})
    if existing_gender is None:
        gender_logger.debug(log_stmt_format.format(service_name, first_name, full_name, 'Name Not Found'))

    elif existing_gender is not None and existing_gender['gender'] in ['female', 'male', 'unknown']:
        ignore_list.append(service_name)
        gender = existing_gender['gender']
        gender_logger.debug(log_stmt_format.format(service_name, first_name, full_name, gender))
        return gender, service_name, ignore_list
    else:
        gender_logger.warning(log_stmt_format.format(service_name, first_name, full_name, 'unknown'))

    # ===== Checking GenderAPI cache on full name
    service_name = 'GenderAPI_FullName'
    existing_gender = genderapi_cache_col.find_one({'q': full_name})

    if existing_gender is None:
        gender_logger.debug(log_stmt_format.format(service_name, first_name, full_name, 'Name Not Found'))
    elif existing_gender is not None and existing_gender['gender'] == 'unknown':
        ignore_list.append(service_name)
        gender_logger.debug(log_stmt_format.format(service_name, first_name, full_name, 'unknown'))
    elif existing_gender is not None and existing_gender['gender'] != 'unknown':
        gender = existing_gender['gender']
        gender_logger.debug(log_stmt_format.format(service_name, first_name, full_name, gender))

        return gender, service_name, ignore_list
    else:
        gender_logger.warning(log_stmt_format.format(service_name, first_name, full_name, 'unknown'))
        ignore_list.append(service_name)

    # ========== Checking first name caches ==========
    if first_name is not None:  # only check for valid first names

        # ===== Checking Genderize cache
        service_name = 'Genderize'
        existing_gender = genderize_cache_col.find_one({'name': first_name})

        if existing_gender is None:
            gender_logger.debug(log_stmt_format.format(service_name, first_name, full_name, 'Name Not Found'))
        elif existing_gender is not None and existing_gender['gender'] == 'unknown':
            ignore_list.append(service_name)
            gender_logger.debug(log_stmt_format.format(service_name, first_name, full_name, 'unknown'))
        elif existing_gender is not None and existing_gender['gender'] != 'unknown':
            gender = existing_gender['gender']
            if gender is None:
                gender = 'unknown'

            gender_logger.debug(log_stmt_format.format(service_name, first_name, full_name, gender))
            return gender, service_name, ignore_list
        else:
            gender_logger.warning(log_stmt_format.format(service_name, first_name, full_name, 'unknown'))
            ignore_list.append(service_name)

        # ===== Checking GenderAPI cache on first name
        service_name = 'GenderAPI_FirstName'
        existing_gender = genderapi_cache_col.find_one({'name': first_name})

        if existing_gender is None:
            gender_logger.debug(log_stmt_format.format(service_name, first_name, full_name, 'Name Not Found'))
        elif existing_gender is not None and existing_gender['gender'] == 'unknown':
            ignore_list.append(service_name)
            gender_logger.debug(log_stmt_format.format(service_name, first_name, full_name, 'unknown'))
        elif existing_gender is not None and existing_gender['gender'] != 'unknown':
            gender = existing_gender['gender']
            gender_logger.debug(log_stmt_format.format(service_name, first_name, full_name, gender))

            return gender, service_name, ignore_list
        else:
            gender_logger.warning(log_stmt_format.format(service_name, first_name, full_name, 'unknown'))
            ignore_list.append(service_name)

        # ===== Checking FirstName cache
        service_name = 'FirstName'
        existing_gender = firstname_cache_col.find_one({'name': first_name})

        if existing_gender is None:
            gender_logger.debug(log_stmt_format.format(service_name, first_name, full_name, 'Name Not Found'))

        elif existing_gender is not None and existing_gender['gender'] == 'unknown':
            ignore_list.append(service_name)
            gender_logger.debug(log_stmt_format.format(service_name, first_name, full_name, 'unknown'))
        elif existing_gender is not None and existing_gender['gender'] != 'unknown':
            gender = existing_gender['gender']
            gender_logger.debug(log_stmt_format.format(service_name, first_name, full_name, gender))

            return gender, service_name, ignore_list
        else:
            gender_logger.warning(log_stmt_format.format(service_name, first_name, full_name, 'unknown'))

    else:
        gender_logger.warning('Can not extract first name from "{0}". Skipping First Name Services.'.format(full_name))

    return 'unknown', 'Hardcode', ignore_list


# The priorities to get gender from services:
# 1. Genderize
# 2. GenderAPI_FullName: GenderAPI based on split API (full name)

def get_gender_from_service(full_name, ignore_list=[]):
    full_name = utils.clean_ne(full_name)
    first_name = utils.extract_first_name(full_name)

    svc_call_log_format = '"{0}" service result for "{1}" is: "{2}"'
    svc_ignore_log_format = 'Ignoring "{0}" service for "{1}"'

    # ---------- Genderize ----------
    service_name = 'Genderize'
    if GENDERIZE_ENABLED and (first_name is not None) and (service_name not in ignore_list):

        gender = get_genderize_gender(full_name)
        gender_logger.debug(svc_call_log_format.format(service_name, full_name, gender))

        if gender != 'unknown':
            return gender, service_name
    else:
        gender_logger.debug(svc_ignore_log_format.format(service_name, full_name))

    # ---------- GenderAPI ----------
    service_name = 'GenderAPI_FullName'
    if GENDERAPI_ENABLED and service_name not in ignore_list:

        gender = get_genderapi_gender(full_name)
        gender_logger.info(svc_call_log_format.format(service_name, full_name, gender))

        if gender != 'unknown':
            return gender, service_name
    else:
        gender_logger.debug(svc_ignore_log_format.format(service_name, full_name))

    return 'unknown', 'Hardcode'


# Deprecated due to low accuracy
def get_viaf_gender(name, maximumRecords=1000):
    name = name.strip().lower()
    if ' ' not in name:
        name = name + ' '  # Add space to handle an exception

    female_count = 0
    male_count = 0
    unknown_count = 0
    final_gender = 'unknown'

    # Get gender from VIAF service
    try:

        some_url = 'http://www.viaf.org/viaf/search?query=cql.any+=+"' + urllib.parse.quote(
            name) + '"&maximumRecords=' + str(maximumRecords) + '&httpAccept=application/json'

        gender_logger.debug('Calling VIAF with: "{0}"'.format(some_url))

        response = urlopen(some_url)

        # Convert bytes to string type and string type to dict
        string = response.read().decode('utf-8')
        json_obj = json.loads(string)

        number_of_records = int(json_obj['searchRetrieveResponse']['numberOfRecords'])

        if number_of_records > 0:

            records = json_obj['searchRetrieveResponse']['records']
            cnt = len(records)

            for i in range(cnt):
                gender = records[i]['record']['recordData']['fixed']['gender']
                if gender == 'a':
                    female_count = female_count + 1
                elif gender == 'b':
                    male_count = male_count + 1
                elif gender == 'u':
                    unknown_count = unknown_count + 1

            if female_count > male_count:
                final_gender = 'female'
            elif male_count > female_count:
                final_gender = 'male'

            gender_logger.debug(
                'VIAF service call result for "{0}": "{1}"\t(female:{2}   male:{3}   unknown:{4}     total:{5})'.format(
                    name,
                    final_gender,
                    female_count, male_count, unknown_count, number_of_records))

        gender_cache = {
            "name": name.strip(),
            "gender": final_gender,
            "femaleCount": female_count,
            "maleCount": male_count,
            "unknownCount": unknown_count}

        viaf_cache_col.insert_one(gender_cache)
        return final_gender
    except:
        gender_logger.exception("message")
        return 'unknown'


def get_genderize_gender(full_name):
    full_name = utils.clean_ne(full_name).lower()
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
            gender = cache_obj['gender']
            gender_logger.debug(
                'Genderize service call result for "{0}" ("{1}"): "{2}"'.format(first_name, full_name, gender))

            # Handle unknowns
            if gender is None:
                gender = 'unknown'
                cache_obj['gender'] = 'unknown'
            # Update Genderize cache
            genderize_cache_col.insert_one(cache_obj)
            return gender
        except:
            gender_logger.exception("message")
            return 'unknown'


def get_genderapi_gender(full_name):
    try:
        full_name = utils.clean_ne(full_name).lower()
        # Create a requests session
        session = requests.Session()
        url = "https://gender-api.com/get?split={}&key={}".format(quote(full_name), GENDERAPI_TOKEN)
        response = session.get(url)
        cache_obj = response.json()
        gender = cache_obj["gender"]
        gender_logger.debug('GenderAPI service call result for "{0}": "{1}"'.format(full_name, gender))

        # Handle unknowns
        if gender is None:
            gender = 'unknown'
            cache_obj['gender'] = 'unknown'
        # Update cache. name attribute in cache_obj contains the name as cache_key
        cache_obj['q'] = full_name
        genderapi_cache_col.insert_one(cache_obj)

    except:
        gender_logger.exception("message")
        gender = 'unknown'

    return gender


if __name__ == '__main__':
    app.run(debug=False, port=GENDER_PORT)