# Extracting quotes, named entities and gender

This directory stores the scripts and methodology used to evaluate quotes and named entities extracted by the NLP pipeline. The earlier version of the evaluation scripts relied on the user running `quote_extractor.py` and `entity_gender_annotator.py` *directly on the database* to generate results, whose results could then be evaluated vs. human annotated data. However, this approach came with some downsides:

* In May 2020, the Discourse Processing Lab collaborated with MDS students from the University of British Columbia to explore ways to improve quote extraction. Due to permissions issues with external vendors, a standalone quote extraction evaluation pipeline had to be used.
* It was decided to use a static copy of the 98 articles to compare any new evaluation results directly with older ones.

## Run the quote extractor
The version of the quote extractor stored in this directory (`quote_extractor_V5.1.py`) contains the exact same methods as the one running on the database in production. However, it looks for a `rawtext/` directory that contains 98 `.txt` files of each article's body field instead. 

Before evaluation, first run the quote extraction pipeline (and any other updated, better pipelines) to generate JSON files that can be compared with the human annotations. 

#### Optional arguments
```sh
python3 quote_extractor_v5.1.py --help
usage: quote_extractor_v5.1.py [-h] [--lang LANG] [--input INPUT]
                               [--output OUTPUT]

optional arguments:
  -h, --help       show this help message and exit
  --lang LANG      spaCy language model to use
  --input INPUT    Path to raw news article data
  --output OUTPUT  Path to raw news article data
```

#### Example run command
The default spaCy language model used to run quote extraction is the same as the one running in production for V5.1 (`en_core_web_lg`), so this argument need not be specified.
```sh
python3 quote_extractor_v5.1.py --input ./rawtext --output ./eval/V5.1
```
This dumps out 98 JSON files containing the extracted quotes and their associated metadata to the directory `./eval/V5.1`.

## Extract named entities and person genders
Evaluating named entities requires an additional step - i.e., gender recognition to be run as well. This is because the human annotated data stores the named entities (people and sources) in separate columns depending on whether they are male or female. So, in essence, evaluating named entities also involves evaluating the *gender* of the named entities themselves. To avoid duplicating large parts of the codebase, this step is performed using the production entity gender annotator script directly on the database.

### Export relevant named entity fields from the database to CSV
For the 98 articles being evaluated, we first run a MongoDB shell command to extract the relevant fields into a CSV file.

```sh
mongoexport -u username -p password --host localhost --authenticationDatabase admin \
-d mediaTracker -c media \
--query '{"_id": {"$in":[ObjectId("5c1452701e67d78e276ee126"),ObjectId("5c146e42795bd2fcce2ea8e5"),ObjectId("5c149ffc1e67d78e276fbd44"),ObjectId("5c1548a31e67d78e2771624f"),ObjectId("5c158f201e67d78e27721ffd"),ObjectId("5c159cb81e67d78e277241fd"),ObjectId("5c182ac21e67d78e277944ad"),ObjectId("5c1dbe1d1e67d78e2797d611"),ObjectId("5c1dccbf1e67d78e279807d8"),ObjectId("5c1de1661e67d78e27984d34"),ObjectId("5c1df61f1e67d78e2798f3fe"),ObjectId("5c1e0b68795bd2a5d03a49a9"),ObjectId("5c1efb3d1e67d78e279bd39a"),ObjectId("5c1f08711e67d78e279bf66d"),ObjectId("5c1f1d831e67d78e279c35b4"),ObjectId("5c1f328f1e67d78e279c7d31"),ObjectId("5c201b371e67d78e279e248a"),ObjectId("5c2059ec1e67d78e279ea86c"),ObjectId("5c2060d31e67d78e279eb852"),ObjectId("5c20ae45795bd2d89328853e"),ObjectId("5c25054e1e67d78e27aac4ef"),ObjectId("5c2858471e67d78e27b3b633"),ObjectId("5c286d031e67d78e27b3f17b"),ObjectId("5c287b841e67d78e27b4163e"),ObjectId("5c2849d21e67d78e27b38ce9"),ObjectId("5c28eba91e67d78e27b54bca"),ObjectId("5c2955161e67d78e27b64992"),ObjectId("5c29947f1e67d78e27b6d330"),ObjectId("5c29beda1e67d78e27b74939"),ObjectId("5c29ccfc1e67d78e27b76bfb"),ObjectId("5c29e8a8795bd2ac48ec6e58"),ObjectId("5c2a3d191e67d78e27b8ac72"),ObjectId("5c2a60611e67d78e27b8feef"),ObjectId("5c2aa6971e67d78e27b9ab24"),ObjectId("5c2ae5f11e67d78e27ba36d7"),ObjectId("5c32f9841e67d78e27cfa4eb"),ObjectId("5c35c63f795bd2d9a887febb"),ObjectId("5c3370aa1e67d78e27d0f869"),ObjectId("5c3377b81e67d78e27d10a65"),ObjectId("5c33859e1e67d78e27d12893"),ObjectId("5c339b091e67d78e27d16414"),ObjectId("5c33e1a71e67d78e27d2193c"),ObjectId("5c3436991e67d78e27d30c2c"),ObjectId("5c344a9f1e67d78e27d34d0a"),ObjectId("5c3474c2795bd22cf5864830"),ObjectId("5c34c2311e67d78e27d50d44"),ObjectId("5c34c92a1e67d78e27d52117"),ObjectId("5c34d7211e67d78e27d54599"),ObjectId("5c3533311e67d78e27d653f4"),ObjectId("5c3d854a1e67d78e27f049d6"),ObjectId("5c3daf32795bd2eb3f0108d8"),ObjectId("5c3e038e1e67d78e27f2105a"),ObjectId("5c3e11b11e67d78e27f2357a"),ObjectId("5c3e27a31e67d78e27f27b38"),ObjectId("5c3eac6f1e67d78e27f3dc55"),ObjectId("5c3ed6b11e67d78e27f46477"),ObjectId("5c3eec791e67d78e27f51065"),ObjectId("5c3f00a6795bd298e67a078f"),ObjectId("5c3f4e281e67d78e27f62b50"),ObjectId("5c3f55241e67d78e27f63e5a"),ObjectId("5c3f78b21e67d78e27f6a477"),ObjectId("5c3fbf491e67d78e27f767d8"),ObjectId("5c3fefc41e67d78e270257d3"),ObjectId("5c47fce51e67d78e271b1f7a"),ObjectId("5c48111c1e67d78e271b6146"),ObjectId("5c48278d1e67d78e271c1a28"),ObjectId("5c483b26795bd2b724e92a68"),ObjectId("5c4888ac1e67d78e271d2cdf"),ObjectId("5c488fac1e67d78e271d405b"),ObjectId("5c489df91e67d78e271d66c5"),ObjectId("5c494e541e67d78e271f514e"),ObjectId("5c4962f31e67d78e271f9498"),ObjectId("5c4977bc1e67d78e27204091"),ObjectId("5c498cc6795bd264151080e0"),ObjectId("5c49e1261e67d78e2721712b"),ObjectId("5c49ef691e67d78e272197a5"),ObjectId("5c4a89f31e67d78e27233c5d"),ObjectId("5c529d681e67d78e273c4cb9"),ObjectId("5c52b36a1e67d78e273d029c"),ObjectId("5c52c73b795bd245ab059d61"),ObjectId("5c5314a91e67d78e273e13be"),ObjectId("5c531ba91e67d78e273e272a"),ObjectId("5c533fe21e67d78e273e92d1"),ObjectId("5c53eea41e67d78e27407cc3"),ObjectId("5c53fcb21e67d78e2740a299"),ObjectId("5c5418cc795bd22bf37ca606"),ObjectId("5c54662d1e67d78e27425afa"),ObjectId("5c546d281e67d78e27426e82"),ObjectId("5c547bf71e67d78e2742971d"),ObjectId("5c5490681e67d78e2742d421"),ObjectId("5c5555d11e67d78e27457a93"),ObjectId("5c5d15151e67d78e275d5d0f"),ObjectId("5c5d292b1e67d78e275d9e9f"),ObjectId("5c5d37341e67d78e275dc30f"),ObjectId("5c5d3e251e67d78e275e54b5"),ObjectId("5c5d532a795bd2d5c282a094"),ObjectId("5c5e50711e67d78e27616b23"),ObjectId("5c5da7aa1e67d78e275f8a3c")]}}' \
--type csv --out  "db_ner_5.1.csv" \
--fields "_id,authors,authorsFemale,authorsMale,authorsUnknown,people,peopleFemale,peopleMale,peopleUnknown,sourcesFemale,sourcesMale,sourcesUnknown"
```
This outputs the relevant named entities organized by gender to a file called `db_ner_v5.1.csv`.

Move this file to the `./eval` directory for evaluation.

## Evaluation of Quotes and Named Entities
See the README.md in `./eval`.
