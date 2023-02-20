# Extracting quotes, named entities and gender

This directory stores the scripts and methodology used to evaluate quotes extraction and named entities identification and gender annotations performed by the English NLP pipeline.

## Prerequisite: Obtain ssh tunnel to the MongoDB database
To run this script locally, it is first required to set up an ssh tunnel that forwards the database connection to the local machine. This step is essential to complete the evaluation because we host a gender lookup cache on our database, which allows us to retrieve existing names and their associated genders.

Set up the database tunnel on a Unix shell as follows. In the example below, `vm12` is the primary database on which the gender cache is hosted. We simply forward the connection from port 27017 on the remote database to the same port on our local machine.

```sh
ssh vm12 -f -N -L 27017:localhost:27017
```

In case database connectivity is not possible, it's possible to rewrite the gender service to only obtain named-based lookups via external gender APIs. However, in such a case, the results might vary from those shown below.
## 1. Produce the annotations
Before evaluating the annotations made by the system, you'll need to produce those annotations. The gender annotation pipeline can be broken down into two successive steps :
- Quote Extraction
- Entity Gender Annotation

The entity gender annotation step takes the output of the quote extraction step as input.
In order to evaluate the performance of each part the pipeline individually, ```run_predictions.py``` can run each part of the pipeline by using the fully accurate input for each step (which is why the target annotations must be passed to the script).
It can also run the whole NLP pipeline.

### Optional Arguments
```sh
python3 run_predictions.py --help
usage: run_predictions.py [-h] [--in_dir IN_DIR] [--out_dir OUT_DIR] [--target_dir TARGET_DIR] [--quote_extraction] [--gender_annotation] [--all] [--spacy_model SPACY_MODEL] [--poolsize POOLSIZE] [--chunksize CHUNKSIZE]

Evaluation of all the steps of the gender annotation pipeline

optional arguments:
  -h, --help            show this help message and exit
  --in_dir IN_DIR       Path to read input text files from this directory.
  --out_dir OUT_DIR     Path to dir to output all predictions
  --target_dir TARGET_DIR
                        Path to json target files. Serve as anchor for intermediate steps of the pipeline.
  --quote_extraction    run quote extractor on text input files
  --gender_annotation   run whole the whole pipeline on text on text input files
  --all                 compute all metrics
  --spacy_model SPACY_MODEL
                        spacy language model
  --poolsize POOLSIZE   Size of the concurrent process pool for the given task
  --chunksize CHUNKSIZE
                        Number of articles per chunk being processed concurrently
```

### Example run command
For V7.0, this is the command used to generate all the needed outputs.
```sh
python3 run_predictions.py --in_dir ./rawtexts/ --target_dir ./eval/humanAnnotations/ --out_dir ./eval/systemAnnotations/V7.0/ --all
```
This dumps out 98 JSON files containing the respective system output in each of these directories : `./eval/systemAnnotations/V7.0/quotes/extracted_quotes`, `./eval/systemAnnotations/V7.0/gender_annotation/entire_pipeline`

## 2. Get the metrics

The script `evaluate.py` must be run after the script `run_predictions.py` has been run.
It is only possible to get the metrics for the predictions that have already been run (for instance, do not specify --gender_annotation in `evaluate.py` if this argument was not specified in `run_predictions.py`)

For more details regarding the way the metrics are computed, see the readme in the `./eval` directory.


### Optional Arguments
```sh
python3 evaluate.py --help 
usage: evaluate.py [-h] [--target_dir TARGET_DIR] [--pred_dir PRED_DIR] [--quote_extraction] [--gender_annotation] [--gender_ratio] [--all]

evaluation of all the steps of the gender annotation pipeline

optional arguments:
  -h, --help            show this help message and exit
  --target_dir TARGET_DIR
                        Path to read input text files from this directory.
  --pred_dir PRED_DIR   Path to write JSON quotes to this directory.
  --quote_extraction    compute metrics on the quote extractor output
  --gender_annotation   compute metrics on the gender annotator on the whole pipeline
  --gender_ratio        compare overall gender ratios between target and output of whole pipeline
  --all                 compute all metrics
```

### Example run command
For V7.0, this is the command used to display the metrics for all parts of the pipeline
```sh
python3 evaluate.py --target_dir eval/humanAnnotations/ --pred_dir eval/systemAnnotations/V7.0/ --all
```
Our latest (best) evaluation produced the metrics shown below.

```
Quote Extraction
----------------------------------------
                     Precision (%)        Recall (%)           F1-Score (%)         Accuracy (%)        
Quotes: 0.3          84.647               82.719               83.672               -                   
Speaker match: 0.3   -                    -                    -                    86.478              
Verb match: 0.3      -                    -                    -                    92.065              
Quotes: 0.8          76.971               75.218               76.084               -                   
Speaker match: 0.8   -                    -                    -                    87.444              
Verb match: 0.8      -                    -                    -                    93.321              
Speakers (indep):    80.672               97.595               88.33                -                   
Verbs (indep):       83.027               88.11                85.493               -                   


Gender Annotation
----------------------------------------
                     Precision (%)        Recall (%)           F1-Score (%)        
peopleFemale         71.939               77.049               74.406              
peopleMale           78.361               92.278               84.752              
peopleUnknown        N/A                  0.0                  N/A                 
sourcesFemale        94.643               64.634               76.812              
sourcesMale          87.805               76.923               82.005              
sourcesUnknown       N/A                  0.0                  N/A                 


Gender Ratio: People
----------------------------------------
                     Male                 Female               Unknown             
Human annotations    0.738                0.261                0.001               
System V7.0          0.758                0.242                0.0                 



Gender Ratio: Sources
----------------------------------------
                     Male                 Female               Unknown             
Human annotations    0.738                0.259                0.003               
System V7.0          0.785                0.215                0.0  
```
