# Extracting quotes, named entities and gender

This directory stores the scripts and methodology used to evaluate quotes extraction and named entities identification and gender annotations performed by the French NLP pipeline.

## Prerequisite: Obtain ssh tunnel to the MongoDB database
To run this script locally, it is first required to set up an ssh tunnel that forwards the database connection to the local machine. This step is essential to complete the evaluation because we host a gender lookup cache on our database, which allows us to retrieve existing names and their associated genders.

Set up the database tunnel on a Unix shell as follows. In the example below, `vm12` is the primary database on which the gender cache is hosted. We simply forward the connection from port 27017 on the remote database to the same port on our local machine.

```sh
ssh vm12 -f -N -L 27017:localhost:27017
```

In case database connectivity is not possible, it's possible to rewrite the gender service to only obtain named-based lookups via external gender APIs. However, in such a case, the results might vary from those shown below.

## 1. Produce the annotations
Before evaluating the annotations made by the system, you'll need to produce those annotations. The gender annotation pipeline can be broken down into three successive steps :
- Quote Extraction
- Quote Merging (Includes Entity Merging)
- Gender Classification

Each of those successive steps takes the output of the previous steps as input.
In order to evaluate the performance of each part the pipeline individually, ```run_predictions.py``` can run each part of the pipeline by using the fully accurate input for each step (which is why the target annotations must be passed to the script).
It can also run the whole gender annotation pipeline.

### Optional Arguments
```sh
python3.9 run_predictions.py --help
usage: run_predictions.py [-h] [--lang LANG] [--in_dir IN_DIR]
                               [--out_dir OUT_DIR] [--target_dir TARGET_DIR]
                               [--quote_extraction QUOTE_EXTRACTION]
                               [--quote_merging QUOTE_MERGING]
                               [--gender_classification GENDER_CLASSIFICATION]
                               [--gender_annotation GENDER_ANNOTATION]
                               [--all]

optional arguments:
  -h, --help       show this help message and exit
  --lang LANG      spaCy language model to use
  --in_dir IN_DIR    Path to raw news article data
  --out_dir OUT_DIR  Path to evaluation output directory
  --target_dir TARGET_DIR  Path to target gender annotations directory
  --quote_extraction    QUOTE_EXTRACTION Run quote extractor on text input files
  --quote_merging QUOTE_MERGING   Run quote merger on text files and target quotes
  --gender_classification GENDER_CLASSIFICATION   run gender classification on target quotes and target people
  --gender_annotation GENDER_ANNOTATION   Run the whole pipeline on text input files
  --all  Run all of the above
```

### Example run command
For V7.0, this is the command used to generate all the needed outputs.
```sh
python3.9 run_predictions.py --in_dir ./rawtexts/ --target_dir ./eval/humanAnnotations/ --out_dir ./eval/systemAnnotations/V7.0/ --all
```
This dumps out 54 JSON files containing the respective system output in each of the 4 directories : `./eval/systemAnnotations/V7.0/quotes/extracted_quotes`, `./eval/systemAnnotations/V7.0/quotes/merged_quotes`, `./eval/systemAnnotations/V7.0/gender_annotation/gender_classification`, `./eval/systemAnnotations/V7.0/gender_annotation/entire_pipeline`

## 2. Get the metrics

The script `evaluate.py` must be run after the script `run_predictions.py` has been run.
It is only possible to get the metrics for the predictions that have already been run (for instance, do not specify --gender_classification in `evaluate.py` if this argument was not specified in `run_predictions.py`)

For more details regarding the way the metrics are computed, see the readme in the `./eval` directory.


### Optional Arguments
```sh
python3.9 evaluate.py --help
usage: evaluate.py [-h] [--lang LANG] [--in_dir IN_DIR]
                               [--out_dir OUT_DIR] [--target_dir TARGET_DIR]
                               [--quote_extraction QUOTE_EXTRACTION]
                               [--quote_merging QUOTE_MERGING]
                               [--gender_classification GENDER_CLASSIFICATION]
                               [--gender_annotation GENDER_ANNOTATION]
                               [--gender_ratio GENDER_RATIO
                               [--all]

optional arguments:
  -h, --help       show this help message and exit
  --out_dir PRED_DIR  Path to the prediction directory
  --target_dir TARGET_DIR  Path to target gender annotations directory
  --quote_extraction    QUOTE_EXTRACTION Evaluate quote extractor
  --quote_merging QUOTE_MERGING   Evaluate Quote Merger
  --gender_classification GENDER_CLASSIFICATION   Evaluate Gender classification
  --gender_annotation GENDER_ANNOTATION   Evaluate gender annotation for the whole pipeline
  --gender_ratio GENDER_RATIO   Compare overall gender ratio between target and output of the whole pipeline
  --all  Evaluate everything
```

### Example run command
For V7.0, this is the command used to display the metrics for all parts of the pipeline
```sh
python3.9 evaluate.py --target_dir eval/humanAnnotations/ --pred_dir eval/systemAnnotations/V7.0/ --all
```
Our latest (best) evaluation produced the metrics shown below.

```
Quote Extraction
----------------------------------------
                     Precision (%)        Recall (%)           F1-Score (%)         Accuracy (%)        
Quotes: 0.3          83.972               79.463               81.655               -                   
Speaker match: 0.3   -                    -                    -                    80.405              
Verb match: 0.3      -                    -                    -                    90.878              
Quotes: 0.8          74.61                70.604               72.552               -                   
Speaker match: 0.8   -                    -                    -                    84.03               
Verb match: 0.8      -                    -                    -                    94.677              
Speakers (indep):    79.167               78.802               78.984               -                   
Verbs (indep):       84.52                83.774               84.145               -                   


Quote Merger
----------------------------------------
                     Precision (%)        Recall (%)           F1-Score (%)        
Speaker Reference    90.27                66.402               76.518              


Gender Classification
----------------------------------------
                     Precision (%)        Recall (%)           F1-Score (%)        
peopleFemale         97.26                97.26                97.26               
peopleMale           99.005               98.515               98.759              
peopleUnknown        N/A                  N/A                  N/A                 
sourcesFemale        97.561               100.0                98.765              
sourcesMale          100.0                97.521               98.745              
sourcesUnknown       N/A                  N/A                  N/A                 


Gender Annotation
----------------------------------------
                     Precision (%)        Recall (%)           F1-Score (%)        
people               97.2                 88.364               92.572              
peopleFemale         92.424               83.562               87.77               
peopleMale           97.283               88.614               92.746              
peopleUnknown        N/A                  N/A                  N/A                 
sources              93.878               57.143               71.043              
sourcesFemale        83.333               50.0                 62.5                
sourcesMale          95.946               58.678               72.821              
sourcesUnknown       N/A                  N/A                  N/A                 


Gender Ratio: People
----------------------------------------
                     Male                 Female               Unknown             
Human annotations    0.735                0.265                0.0                 
System V7.0          0.736                0.264                0.0                 



Gender Ratio: Sources
----------------------------------------
                     Male                 Female               Unknown             
Human annotations    0.753                0.247                0.0                 
System V7.0          0.755                0.245                0.0
```
