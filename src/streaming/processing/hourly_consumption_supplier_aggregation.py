"""
Aggregate hourly consumption supplier
"""

# %%
import json
import time
import urllib.parse

import configargparse
from datetime import datetime
from pyspark import SparkConf
from pyspark.sql import DataFrame, SparkSession

# %%
p = configargparse.ArgParser(prog='hourly_consumption_supplier_aggregation.py', description='Green Energy Hub Hourly Consumption Supplier Aggregation',
                             default_config_files=['configuration/run_args_hourly_consumption_supplier.conf'],
                             formatter_class=configargparse.ArgumentDefaultsHelpFormatter)
p.add('--input-storage-account-name', type=str, required=True,
      help='Azure Storage account name holding time series data')
p.add('--input-storage-account-key', type=str, required=True,
      help='Azure Storage key for input storage', env_var='GEH_INPUT_STORAGE_KEY')
p.add('--input-storage-container-name', type=str, required=False, default='data',
      help='Azure Storage container name for input storage')
p.add('--input-path', type=str, required=False, default="delta/meter-data/",
      help='Path to time series data storage location (deltalake) relative to root container')
p.add('--output-storage-account-name', type=str, required=True,
      help='Azure Storage account name holding aggregations')
p.add('--output-storage-account-key', type=str, required=True,
      help='Azure Storage key for output storage', env_var='GEH_OUTPUT_STORAGE_KEY')
p.add('--output-storage-container-name', type=str, required=False, default='aggregations',
      help='Azure Storage container name for output storage')
p.add('--output-path', type=str, required=False, default="delta/hourly-consumption-supplier/",
      help='Path to aggregation storage location (deltalake) relative to root container')
p.add('--beginning-date-time', type=str, required=True,
      help='The timezone aware date-time representing the beginning of the time period of aggregation (ex: 2020-01-03T00:00:00+0100)')
p.add('--end-date-time', type=str, required=True,
      help='The timezone aware date-time representing the end of the time period of aggregation (ex: 2020-01-03T00:00:00-0100)')

args, unknown_args = p.parse_known_args()

# Parse the given date times
date_time_formatting_string = "%Y-%m-%dT%H:%M:%S%z"
end_date_time = datetime.strptime(args.end_date_time, date_time_formatting_string)
beginning_date_time = datetime.strptime(args.beginning_date_time, date_time_formatting_string)

if unknown_args:
    print("Unknown args:")
    _ = [print(arg) for arg in unknown_args]

# %%

# Set spark config with storage account names/keys and the session timezone so that datetimes are displayed consistently (in UTC)
spark_conf = SparkConf(loadDefaults=True) \
    .set('fs.azure.account.key.{0}.blob.core.windows.net'.format(args.input_storage_account_name),
         args.input_storage_account_key) \
    .set('fs.azure.account.key.{0}.blob.core.windows.net'.format(args.output_storage_account_name),
         args.output_storage_account_key) \
    .set("spark.sql.session.timeZone", "UTC")

spark = SparkSession\
    .builder\
    .config(conf=spark_conf)\
    .getOrCreate()

sc = spark.sparkContext
print("Spark Configuration:")
_ = [print(k + '=' + v) for k, v in sc.getConf().getAll()]

# %%
# Create input and output storage paths

INPUT_STORAGE_PATH = "wasbs://{0}@{1}.blob.core.windows.net/{2}".format(
    args.input_storage_container_name, args.input_storage_account_name, args.input_path
)

print("Input storage url:", INPUT_STORAGE_PATH)

OUTPUT_STORAGE_PATH = "wasbs://{0}@{1}.blob.core.windows.net/{2}".format(
    args.output_storage_container_name, args.output_storage_account_name, args.output_path
)

print("Output storage url:", OUTPUT_STORAGE_PATH)

# %%

# Read in time series data (delta doesn't support user specified schema)
timeseries_df = spark \
    .read \
    .format("delta") \
    .load(INPUT_STORAGE_PATH)

# %%
from aggregation_utils.filters import TimePeriodFilter

# Filter out time series data that is not in the specified time period
valid_time_period_df = TimePeriodFilter.filter(timeseries_df, beginning_date_time, end_date_time)

# %%
from aggregation_utils.aggregators import HourlyConsumptionSupplierAggregator

# Perform aggregation calculation
aggregated_df = HourlyConsumptionSupplierAggregator.aggregate(valid_time_period_df)

# %%

# Write out to delta storage
# TODO: discuss partitioning plan, if necessary - Issue #256
aggregated_df \
    .write \
    .format("delta") \
    .save(OUTPUT_STORAGE_PATH)

# %%
