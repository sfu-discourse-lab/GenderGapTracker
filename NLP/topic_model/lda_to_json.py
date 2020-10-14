import argparse
import os
import json
from datetime import datetime
from pyspark.ml import Pipeline
from pyspark.ml.clustering import LDA
from pyspark.ml.feature import (
    CountVectorizer, RegexTokenizer,
    IDF, StopWordsRemover
)
from pyspark.sql import SparkSession
import pyspark.sql.functions as f
import pyspark.sql.types as t
# Spark NLP - see full list of importable modules here:
# https://github.com/JohnSnowLabs/spark-nlp/tree/master/python/sparknlp)
from sparknlp.annotator import Tokenizer, Lemmatizer
from sparknlp.base import DocumentAssembler, Finisher
# Config
from config import config

# Path to parquet files containing news article data
root_dir = "./"
dataloc = os.path.join(root_dir, "ggt_english_2018-10-01_2020-04-20")


def write_json(json_object, filename):
    with open(filename, 'w') as f:
        json.dump(json_object, f)


def timestampRangeDF(df, begin_date, end_date):
    """Subset the full data to all articles published later than a
       start timestamp and earlier than an end timestamp.
    """
    start = "{} 00:00:00".format(begin_date)
    end = "{} 23:59:59".format(end_date)
    filteredDF = df.filter(f.col("timestamp") > f.unix_timestamp(
                           f.lit(start)).cast('timestamp')) \
        .filter(f.col("timestamp") < f.unix_timestamp(
                f.lit(end)).cast('timestamp'))
    return filteredDF


def run_spark_preproc_pipeline(df, stopwordfile):
    """Perform tokenization and stopword removal custom regex in Spark"""
    tokenizer = RegexTokenizer(
        inputCol="body",
        outputCol="words",
        pattern="[A-Za-z0-9\-]{3,50}",  # only alphanumeric hyphenated text with 3 or more chars
        gaps=False
    )

    stopwords = sc.textFile(stopwordfile).collect()
    remover = StopWordsRemover(inputCol="words", outputCol="words_filtered")
    remover.setStopWords(stopwords)

    preprocPipeline = Pipeline(stages=[tokenizer, remover])
    wordsDF = preprocPipeline.fit(df).transform(df)
    # Concatenate list of words into a single word for downstream Spark-NLP pipeline
    preprocDF = wordsDF.withColumn("words_joined", f.concat_ws(" ", "words_filtered"))
    return preprocDF


def run_nlp_pipeline(df):
    """Perform lemmatization using Spark-NLP (add-on library)"""
    document_assembler = DocumentAssembler() \
        .setInputCol("words_joined")

    # Obtain tokens from a string
    tokenizer = Tokenizer() \
        .setInputCols(["document"]) \
        .setOutputCol("token")

    # Use spaCy lemma dictionary to train Spark NLP lemmatizer
    lemmatizer = Lemmatizer() \
        .setInputCols(["token"]) \
        .setOutputCol("lemma") \
        .setDictionary(LEMMAS, key_delimiter="->", value_delimiter="\s+", read_as="TEXT")

    finisher = Finisher() \
        .setInputCols(["lemma"]) \
        .setIncludeMetadata(False)

    nlpPipeline = Pipeline(stages=[document_assembler, tokenizer, lemmatizer, finisher])
    nlpPipelineDF = nlpPipeline.fit(df) \
        .transform(df) \
        .withColumnRenamed('finished_lemma', 'allTokens')
    return nlpPipelineDF


def run_ml_pipeline(nlpPipelineDF, num_topics, max_iterations, vocabSize, minDF, maxDF):
    """Define a Spark LDA topic modelling pipeline"""
    cv = CountVectorizer(inputCol="allTokens",
                         outputCol="features",
                         vocabSize=vocabSize,
                         minDF=minDF,
                         maxDF=maxDF,
                         minTF=1.0,
                         )
    idf = IDF(inputCol="features", outputCol="idf")
    lda = LDA(k=num_topics,
              maxIter=max_iterations,
              optimizer="online",
              seed=1,
              learningOffset=100.0,  # If high, early iterations are downweighted during training
              learningDecay=0.51,    # Set between [0.5, 1) to guarantee asymptotic convergence
              )

    mlPipeline = Pipeline(stages=[cv, idf, lda])
    mlModel = mlPipeline.fit(nlpPipelineDF)
    ldaModel = mlModel.stages[2]
    return mlModel, ldaModel


def describe_topics(mlModel):
    """Obtain topic words and weights from the LDA model.

       Returns: topics -> List[Dict[str, float]]
       A list of mappings between the top 15 topic words (str) and their weights
       (float) for each topic. The length of the list equals the number of topics.
    """
    # Store vocab from CountVectorizer
    vocab = mlModel.stages[0].vocabulary
    # Store LDA model part of pipeline
    ldaModel = mlModel.stages[2]

    # Take top 15 words in each topic
    topics = ldaModel.describeTopics(15)
    topics_rdd = topics.rdd

    topic_words = topics_rdd \
        .map(lambda row: row['termIndices']) \
        .map(lambda idx_list: [vocab[idx] for idx in idx_list]) \
        .collect()

    topic_weights = topics_rdd \
        .map(lambda row: row['termWeights']) \
        .collect()

    # Store topic words and weights as a list of dicts
    topics = [dict(zip(words, weights))
              for words, weights in zip(topic_words, topic_weights)]
    return topics


def get_topic_summary_dict(topics, params):
    topic_dict = {}
    words_and_weights = {}
    # Add summary parameters to topic JSON
    topic_dict['params'] = params
    for num, data in enumerate(topics):
        words_and_weights[str(num + 1)] = data
    topic_dict['topics'] = words_and_weights
    return topic_dict


def get_most_dominant_topic(mlPipelineDF):
    """Obtain topic distribution per document"""
    @f.udf(t.IntegerType())
    def sort_indices(topicVectors):
        "Extract indices of topic weights and sort by max weight-value"
        ordered = topicVectors.argsort()[-len(topicVectors):][::-1]
        ordered += 1    # Increment by one to start numbering topics from 1
        return ordered.tolist()[0]

    # Apply udf to create a new DataFrame column that holds the most dominant topic numbers for each document
    dominantTopicsDF = mlPipelineDF.withColumn('mostDominantTopic', sort_indices(mlPipelineDF.topicDistribution))
    return dominantTopicsDF


def split_distribution(df, mlModel, ldaModel):
    """Split the topic distribution vector into individual columns"""
    @f.udf(t.DoubleType())
    def i_th(vector, i):
        # Return the float value at the specified index 'i' of a vector
        return float(vector[i])

    transformedDF = mlModel.transform(df)
    # Calculate upper bound on model perplexity
    ldaPerplexity = ldaModel.logPerplexity(transformedDF)

    # Subset transformed DataFrame to obtain document-topic matrix
    transformedDFSubset = transformedDF.select(
        'id', 'url', 'timestamp', 'outlet', 'title',
        'topicDistribution', 'sourcesFemaleCount', 'sourcesMaleCount'
    )
    # Split topic distribution into individual columns
    splitDF = transformedDFSubset.select('*', *[i_th('topicDistribution', f.lit(i))
                                         for i in range(num_topics)])
    # Rename columns to more human-readable names like "t1", "t2", etc.
    current_colnames = [item[0] for item in transformedDFSubset.dtypes]
    added_colnames = ['t' + str(i + 1) for i in range(num_topics)]
    new_names = current_colnames + added_colnames
    renamedDF = splitDF.toDF(*new_names)
    return renamedDF, ldaPerplexity


def groupby_outlet_topics(topicsDF):
    """Obtain mean topic distribution grouped by outlet. This is done by taking the mean
       of the per-document topic distribution for each outlet that published the article.
       we also store the sum of all sources per gender per outlet for later visualizations.
    """
    mean_topics = [f.mean("t" + str(i + 1)) for i in range(num_topics)]
    count_sources = [f.sum(col) for col in ['sourcesFemaleCount', 'sourcesMaleCount']]
    count_articles_per_outlet = [f.count('outlet').alias('numArticles')]
    aggregator = count_articles_per_outlet + count_sources + mean_topics
    outletDF = topicsDF.groupBy('outlet').agg(*aggregator)
    return outletDF


def groupby_gender_topics(femaleSourcesDF, maleSourcesDF):
    """Group by mean topic distribution per topic per gender"""
    femaleAgg = femaleSourcesDF.agg(*[f.mean("t" + str(i + 1))
                                    for i in range(num_topics)])
    maleAgg = maleSourcesDF.agg(*[f.mean("t" + str(i + 1))
                                for i in range(num_topics)])
    # Rename columns
    colnames = [str(i + 1) for i in range(num_topics)]
    femaleTopicsDF = femaleAgg.toDF(*colnames)
    maleTopicsDF = maleAgg.toDF(*colnames)
    return femaleTopicsDF, maleTopicsDF


def groupby_outlet_gender_topics(femaleSourcesDF, maleSourcesDF):
    """Group by mean topic distribution per outlet per gender"""
    femaleAgg = groupby_outlet_topics(femaleSourcesDF)
    maleAgg = groupby_outlet_topics(maleSourcesDF)
    # Rename columns
    colnames = ["outlet", "numArticles"] + \
               ['totalFemaleSources', 'totalMaleSources'] + \
               [str(i + 1) for i in range(num_topics)]
    outletFemaleGroupedDF = femaleAgg.toDF(*colnames)
    outletMaleGroupedDF = maleAgg.toDF(*colnames)
    return outletFemaleGroupedDF, outletMaleGroupedDF


def get_mean_outlet_dict(outletDF):
    """Reshape the mean topic distribution per outlet as a JSON/dict object"""
    topic_ids = tuple(str(i + 1) for i in range(num_topics))
    mean_outlet_dict = {}
    for item in outletDF.collect():
        outlet = item[0]
        topics = item[4:]
        dist = dict(zip(topic_ids, topics))
        mean_outlet_dict[outlet] = dist
    return mean_outlet_dict


def get_mean_gender_dict(femaleTopicsDF, maleTopicsDF):
    """Reshape the mean topic distribution per gender as a JSON/dict object"""
    mean_gender_dict = {}
    femaleTopics = json.loads(femaleTopicsDF.toJSON().first())
    maleTopics = json.loads(maleTopicsDF.toJSON().first())
    mean_gender_dict['female'] = femaleTopics
    mean_gender_dict['male'] = maleTopics
    return mean_gender_dict


def get_mean_outlet_gender_dict(outlet_genderDF):
    """Reshape the mean topic distribution per outlet and gender as a JSON/dict object"""
    topic_ids = tuple(str(i + 1) for i in range(num_topics))

    outlet_topic_dict = {}
    for item in outlet_genderDF.collect():
        outlet_dict = {}
        outlet_name = item[0]
        num_articles = item[1]
        topics = item[4:]
        topic_distribution = dict(zip(topic_ids, topics))
        outlet_dict['num_articles'] = num_articles
        outlet_dict['topic_mean'] = topic_distribution
        outlet_topic_dict[outlet_name] = outlet_dict
    return outlet_topic_dict


def get_female_dominant_sources(topicsDF, delta=1):
    """Filter articles with more female than male sources in them.
       Requires a DataFrame containing topic distributions
    """
    femaleSourcesDF = topicsDF.drop('topicDistribution') \
        .filter('sourcesFemaleCount - sourcesMaleCount >= {}'.format(delta))
    return femaleSourcesDF


def get_male_dominant_sources(topicsDF, delta=1):
    """Filter articles with more male than female sources in them.
       Requires a DataFrame containing topic distributions
    """
    maleSourcesDF = topicsDF.drop('topicDistribution') \
        .filter('sourcesMaleCount - sourcesFemaleCount >= {}'.format(delta))
    return maleSourcesDF


def top500_female_dominant(topicsDF):
    """Store the subset of articles that have more female sources than male.
       The resulting DataFrame is sorted in desending order of female sources.
    """
    sortedDF = topicsDF.drop('topicDistribution') \
        .filter('sourcesFemaleCount - sourcesMaleCount >= 1') \
        .orderBy(f.col("sourcesFemaleCount"), ascending=False).limit(500)
    return sortedDF


def top500_male_dominant(topicsDF):
    """Store the subset of articles that have more male sources than female.
       The resulting DataFrame is sorted in desending order of male sources.
    """
    sortedDF = topicsDF.drop('topicDistribution') \
        .filter('sourcesMaleCount - sourcesFemaleCount >= 1') \
        .orderBy(f.col("sourcesMaleCount"), ascending=False).limit(500)
    return sortedDF


def write_gender_dominantDF(topicsDF, output_dir):
    """Write CSV files containing the topic distribution based on dominant source gender."""
    femaleDomDF = top500_female_dominant(topicsDF)
    maleDomDF = top500_male_dominant(topicsDF)
    # Write data to CSV
    femaleDomDF.write.mode('overwrite').csv(output_dir, header=True)
    maleDomDF.write.mode('append').csv(output_dir, header=True)


def train():
    # Read DataFrame and store metrics
    df = spark.read.parquet(dataloc)
    filteredDF = timestampRangeDF(df, begin_date, end_date)
    preprocDF = run_spark_preproc_pipeline(filteredDF, STOPWORDS)
    # Run NLP and ML pipelines
    nlpPipelineDF = run_nlp_pipeline(preprocDF).persist()
    article_count = nlpPipelineDF.count()
    mlModel, ldaModel = run_ml_pipeline(nlpPipelineDF, num_topics, max_iterations, vocabSize, minDF, maxDF)

    # Describe topics
    topics = describe_topics(mlModel)
    # Group mean topic distribution by outlet
    topicsDF, ldaPerplexity = split_distribution(nlpPipelineDF, mlModel, ldaModel)
    outletDF = groupby_outlet_topics(topicsDF)
    # Group mean topic distribution by gender
    femaleSourcesDF = get_female_dominant_sources(topicsDF, delta=gender_delta)
    maleSourcesDF = get_male_dominant_sources(topicsDF, delta=gender_delta)
    femaleTopicsDF, maleTopicsDF = groupby_gender_topics(femaleSourcesDF, maleSourcesDF)
    # Group mean topic distribution by outlet and gender
    outletFemaleDF, outletMaleDF = groupby_outlet_gender_topics(femaleSourcesDF, maleSourcesDF)

    # Store topic model params
    topic_params = {
        'begin_date': begin_date,
        'end_date': end_date,
        'num_topics': num_topics,
        'iterations': max_iterations,
        'vocabSize': vocabSize,
        'minDF': minDF,
        'maxDF': maxDF,
        'maxPerplexity': ldaPerplexity,
        'articleCount': article_count,
    }

    if save_model:
        # Save model (if required for later use)
        mlModel.write().save("{}_{}-model".format(prefix, suffix))
        # Dominant topics
        # splits = splitDF.drop('topicDistribution').toPandas()
        # splits.to_csv("split-output.csv", index=False)

    # Store intermediate JSON
    topic_dict = get_topic_summary_dict(topics, topic_params)
    mean_outlet_dict = get_mean_outlet_dict(outletDF)
    mean_gender_dict = get_mean_gender_dict(femaleTopicsDF, maleTopicsDF)
    outlet_female_dict = get_mean_outlet_gender_dict(outletFemaleDF)
    outlet_male_dict = get_mean_outlet_gender_dict(outletMaleDF)
    mean_outlet_gender_dict = {'female': outlet_female_dict, 'male': outlet_male_dict}

    # Write results
    write_json(topic_dict, "{}_{}-topic.json".format(prefix, suffix))
    if store_outlet_log:
        write_json(mean_outlet_dict, "{}_{}-outlet.json".format(prefix, suffix))
    if store_gender_log:
        write_json(mean_gender_dict, "{}_{}-gender.json".format(prefix, suffix))
    if store_outlet_gender_log:
        write_json(mean_outlet_gender_dict, "{}_{}-outlet-gender.json".format(prefix, suffix))
    print("\n***Processed {} articles. Max upper bound on perplexity: {}***".format(article_count, ldaPerplexity))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--topics", type=int, default=15, help="Number of topics for LDA")
    parser.add_argument("--iter", type=int, default=150, help="Max. LDA iterations")
    parser.add_argument("--vocab", type=int, default=5000, help="Max. LDA vocabSize")
    parser.add_argument("--minDF", type=float, default=0.02, help="Min. term document frequency")
    parser.add_argument("--maxDF", type=float, default=0.8, help="Max. term document frequency")
    parser.add_argument("--partitions", type=int, default=100, help="Number of shuffle partitions in PySpark")
    parser.add_argument("--begin_date", type=str, default="2020-01-01", help="Start date")
    parser.add_argument("--end_date", type=str, default="2020-01-31", help="End date")
    parser.add_argument("--gender_delta", type=int, default=1, help="Define delta for male/female source-dominant articles")
    parser.add_argument("--disable_outlet_log", action="store_false", help="Do not write log containing topic distribution per outlet")
    parser.add_argument("--disable_gender_log", action="store_false", help="Do not write log containing topic distribution per gender")
    parser.add_argument("--disable_outlet_gender_log", action="store_false", help="Do not write log containing topic distribution per outlet AND gender")
    parser.add_argument("--save_model", action="store_true", help="Save topic model trained on the given time-range's data")

    args = vars(parser.parse_args())
    # Rename inputs
    num_topics = args['topics']
    max_iterations = args['iter']
    vocabSize = args['vocab']
    minDF = args['minDF']
    maxDF = args['maxDF']
    begin_date = args['begin_date']
    end_date = args['end_date']
    gender_delta = args['gender_delta']
    store_outlet_log = args['disable_outlet_log']
    store_gender_log = args['disable_gender_log']
    store_outlet_gender_log = args['disable_outlet_gender_log']
    save_model = args['save_model']
    # Store year and month for file prefix
    prefix = datetime.strptime(begin_date, '%Y-%m-%d').strftime('%Y-%m-%d')
    suffix = datetime.strptime(end_date, '%Y-%m-%d').strftime('%Y-%m-%d')

    # Read config
    STOPWORDS = config['MODEL']['STOPWORDS']
    LEMMAS = config['MODEL']['LEMMAS']

    spark = SparkSession.builder \
                        .appName("TopicModel-SparkNLP") \
                        .config("spark.shuffle.io.maxRetries", 20) \
                        .config("spark.shuffle.io.retryWait", "20s") \
                        .config("spark.buffer.pageSize", "2m") \
                        .config("spark.sql.shuffle.partitions", args['partitions']) \
                        .getOrCreate()
    sc = spark.sparkContext
    # Train topic model
    train()
    # Stop Spark
    spark.stop()

    # Example run command
    # spark-submit --packages com.johnsnowlabs.nlp:spark-nlp_2.11:2.4.5 train_cc.py --begin_date 2020-01-01 --end_date 2020-01-31
