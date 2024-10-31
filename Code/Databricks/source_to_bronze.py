# Databricks notebook source
# MAGIC %run "/Workspace/Users/andrewkravchuk@outlook.com/dev/nb_common"

# COMMAND ----------

# MAGIC %md
# MAGIC ##### **Get** Stock Data from API

# COMMAND ----------

from pyspark.sql.types import StructType, StructField, ArrayType
from pyspark.sql.types import StringType, DecimalType, IntegerType, DateType

# Create scheme 

meta_schema = StructType( 
           [
               StructField('symbol',StringType(), True),
               StructField('interval',StringType(), True), 
               StructField('currency',StringType(), True), 
               StructField('exchange_timezone',StringType(), True), 
               StructField('exchange',StringType(), True), 
               StructField('mic_code',StringType(), True), 
               StructField('type',StringType(), True)

           ]
)

values_schema = ArrayType(StructType( 
           [
               StructField('datetime',StringType(), True),
               StructField('open',StringType(), True), 
               StructField('high',StringType(), True), 
               StructField('low',StringType(), True), 
               StructField('close',StringType(), True), 
               StructField('volume',StringType(), True)
           ]
) )


schema = StructType(
                    [
                    StructField( 'meta', meta_schema, True),
                    StructField('values', values_schema, True), 
                    StructField('status', StringType(), True)   
                   ])

# df = spark.createDataFrame(all_datatest, schema)
# Load JSON data with the schema


# COMMAND ----------


import time
# Run SQL query from Python
today_date = spark.sql("SELECT date_format(current_date()+2, 'yyyy-MM-dd') AS current_date")

today_date = today_date.collect()[0]["current_date"]


date_3days_before_today = spark.sql("SELECT date_format(current_date()-3, 'yyyy-MM-dd') AS current_date")

date_3days_before_today = date_3days_before_today.collect()[0]["current_date"]
# Access the collected data



# Assume the generated time_ranges are available

time_ranges = [
    (date_3days_before_today, today_date)
]

ADLS_Controller = ADLSController(storage_account="andrewstockmarket")


# Two lists of stock symbols
# list_of_symbols = ["AAPL","VOO"]
# list_of_symbols = ["SPY", "QQQ", "VOO", "EFA", "SCHB", "AGG", "VUG", "VNQ", "GLD"]
list_of_symbols = ["AAPL","VOO","MSFT", "NVDA","TSLA", "TM", "F", "JPM", "GS", "MS"]


# Combine both lists into a list of lists for easy looping
# list_of_symbol_groups = [list_of_symbols_1, list_of_symbols_2, list_of_symbols_3, list_of_symbols_4]

# Initialize GetStockData object with your API key
stock_data = GetStockData("23c1a7c2da0148c584eac977ac756432")

# Outer loop for each symbol group
# all_data = []  # List to store data from all symbol groups and time ranges


for start_date, end_date in time_ranges:
    # Fetch historical stock data for the current time range and symbol group
    data = stock_data.get_historical_stock_data("1day", list_of_symbols, start_date, end_date)
    ADLS_Controller.save_parquet_by_symbol(json_list= data, container_name='bronze', schema=schema)

    # all_data.append(data)  # Store the fetched dat
   
# all_data now contains historical data for both symbol groups and all time ranges
# If needed, print the entire result
# print(json.dumps(all_data, indent=4))


# COMMAND ----------

# display(dbutils.fs.ls("abfss://bronze@andrewstockmarket.dfs.core.windows.net"))


# COMMAND ----------

# df = spark.read.format('parquet') \
#     .load("abfss://bronze@andrewstockmarket.dfs.core.windows.net/VOO")

# display(df)    

# COMMAND ----------

# MAGIC %md
# MAGIC ##### Create Connetion with Data Lake Gen2

# COMMAND ----------

# Initialize the configuration object


# COMMAND ----------

# # Initialize the configuration object
# ADLSController = ADLSController(
#     kv_scope="kv-stock-market", 
#     storage_account="andrewstockmarket", 
#     client_secret_key="spn-stockmarket-storage-access-clientsecret",
#     client_id_key="spn-stockmarket-storage-access-clientid",
#     tenant_id_key="spn-stockmarket-storage-access-tenantid"
# )


# COMMAND ----------

# from pyspark.sql.functions import min

# df = spark.read.format("delta") \
#     .load("abfss://gold@andrewstockmarket.dfs.core.windows.net/fact_stock_price")

# display(df)

