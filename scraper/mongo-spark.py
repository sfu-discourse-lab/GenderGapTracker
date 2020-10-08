import argparse
import getpass
from pyspark.sql.types import *
from pyspark.sql import SparkSession
from sshtunnel import SSHTunnelForwarder

# spark-submit --master yarn --conf=spark.pyspark.virtualenv.enabled=true --conf spark.pyspark.virtualenv.type=native --conf spark.pyspark.virtualenv.requirements="requirements.txt" --conf spark.pyspark.virtualenv.bin.path=/cvmfs/soft.computecanada.ca/custom/bin/virtualenv --conf=spark.pyspark.python=/cvmfs/soft.computecanada.ca/nix/var/nix/profiles/16.09/bin/python --driver-memory 32G  --num-executors 8 --executor-cores 1 --executor-memory 50GB --conf "spark.executor.extraJavaOptions=-Xss2040m"  --packages org.mongodb.spark:mongo-spark-connector_2.11:2.4.1 test.py --output_dir file:///scratch/XXX/21-04-2020-ggt.parquet --spk_sample_size 50000

def main():


    parser = argparse.ArgumentParser(description="Copy Mongo GGT Database format and transform it to parquet files")
    parser.add_argument("--db_host", type=str, default="rcg-vm0012.dcr.sfu.ca")
    parser.add_argument("--db_port", type=int, default=27017)
    parser.add_argument("--db_local_host", type=str, default="bd-node-1")
    parser.add_argument("--tunnel_host", type=str, default="rcg-gt-gateway.dcr.sfu.ca")
    parser.add_argument("--tunnel_port", type=int, default=3222)
    parser.add_argument("--db_user", type=str, default="g-tracker")
    parser.add_argument("--db_password", type=str, default="_tracker-gt")
    parser.add_argument("--db_collection", type=str, nargs="+", default="media")
    parser.add_argument("--db_database", type=str, default="mediaTracker")
    parser.add_argument("--db_auth_db", type=str, default="admin")
    parser.add_argument("--spk_sample_size", type=int, default=50000)
    parser.add_argument("--spk_partitions", type=int,  default=200)
    parser.add_argument("--output_dir", type=str, default="ggt-31-01-2020.parquet")

    args = vars(parser.parse_args())
    tunnel_user = raw_input("Enter ssh tunnel user:")
    tunnel_pswd = getpass.getpass(prompt="Enter ssh tunnel pasword")

    print("Arguments:", args)

    with SSHTunnelForwarder(
            (args["tunnel_host"], args["tunnel_port"]),
            ssh_username=tunnel_user,
            ssh_password=tunnel_pswd,
            remote_bind_address=(args["db_host"], args["db_port"])) as server:

        args.update({"local_port": server.local_bind_port})
        args.update({"local_host": args['db_local_host']})
        print("mongodb://{db_user}:{db_password}@{db_local_host}:{local_host}/{db_auth_db}".format(**args))
        print("mongodb://{db_user}:{db_password}@{db_local_host}:{local_host}/{db_database}.{db_collection}/?authSource={db_auth_db}".format(**args))

        spark = SparkSession \
            .builder \
            .appName("Spark and mongo") \
            .config("spark.mongodb.auth.uri", "mongodb://{db_user}:{db_password}@{local_host}:{local_port}/{db_auth_db}".format(**args)) \
            .config("spark.mongodb.input.uri",
                    "mongodb://{db_user}:{db_password}@{local_host}:{local_port}/{db_database}.{db_collection}?authSource={db_auth_db}".format(**args)) \
            .config('spark.jars.packages', 'org.mongodb.spark:mongo-spark-connector_2.11:2.4.1')\
            .getOrCreate()

        # df = spark.read.format("mongo").load()
        df = spark.read.format("mongo").option('sampleSize', args["spk_sample_size"]).load()
#        df.show(
        df = df.repartition(args["spk_partitions"])
        df.write.parquet(args["output_dir"])


# Main function calling
if __name__ == "__main__":
    main()

