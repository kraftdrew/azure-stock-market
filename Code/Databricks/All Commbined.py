# Databricks notebook source
import uuid
from pyspark.sql.functions import lit, explode, col,to_timestamp, current_timestamp
from pyspark.sql import SparkSession
from pyspark.sql.types import DoubleType, TimestampType, IntegerType


class ADLSController:
    # def __init__(self, kv_scope, storage_account, client_secret_key, client_id_key, tenant_id_key, bronze_container_name="bronze", silver_container_name="silver", 
    #              gold_container_name="gold" ):
    def __init__(self, storage_account, bronze_container_name="bronze", silver_container_name="silver", gold_container_name="gold" ):
        # self.kv_scope = kv_scope
        self.storage_account = storage_account
        # self.client_secret = dbutils.secrets.get(scope=self.kv_scope, key=client_secret_key)
        # self.client_id = dbutils.secrets.get(scope=self.kv_scope, key=client_id_key)
        # self.tenant_id = dbutils.secrets.get(scope=self.kv_scope, key=tenant_id_key) 
        self.bronze_container_name = bronze_container_name
        self.silver_container_name = silver_container_name
        self.gold_container_name = gold_container_name
        
        # self.apply_configs()
    
    # def apply_configs(self):

    #     spark.conf.set(f"fs.azure.account.oauth2.client.id.{self.storage_account}.dfs.core.windows.net", self.client_id)
    #     spark.conf.set(f"fs.azure.account.oauth.provider.type.{self.storage_account}.dfs.core.windows.net", "org.apache.hadoop.fs.azurebfs.oauth2.ClientCredsTokenProvider")
    #     spark.conf.set(f"fs.azure.account.oauth2.client.endpoint.{self.storage_account}.dfs.core.windows.net", f'https://login.microsoftonline.com/{self.tenant_id}/oauth2/token')
    #     spark.conf.set(f"fs.azure.account.oauth2.client.secret.{self.storage_account}.dfs.core.windows.net", self.client_secret)
    #     spark.conf.set(f"fs.azure.account.auth.type.{self.storage_account}.dfs.core.windows.net", "OAuth")
    
    def list_files(self, container_name):
        return dbutils.fs.ls(f"abfss://{container_name}@{self.storage_account}.dfs.core.windows.net") 
    
    def save_parquet_by_symbol(self, json_list, container_name, schema = None):
        """
        Saves the JSON data to ADLS in a folder structure by symbol.
        
        :param json_list: List of JSON objects.
        :param container_name: Name of the ADLS container.
        """

        # Convert the list of JSON objects to a Spark DataFrame
        if schema is None:
            df = spark.createDataFrame(json_list )
        else:
            df = spark.createDataFrame(json_list, schema)

        

        # Loop through the distinct symbols and save data for each symbol
        for symbol in df.select("meta.symbol").distinct().collect():
            symbol_value = symbol[0]  # Extract the symbol value

            # Filter data for each symbol
            symbol_df = df.filter(col("meta.symbol") == symbol_value)

            
            # Define the path dynamically based only on the symbol
            symbol_df.write.mode("append").parquet(
                f"abfss://{container_name}@{self.storage_account}.dfs.core.windows.net/{symbol_value}/"
            ) 



    def bronze_to_silver_delta(self, bronze_container_name: str = None, silver_container_name: str = None):

        if bronze_container_name is None:
            bronze_container_name = self.bronze_container_name
        
        if silver_container_name is None:
            silver_container_name = self.silver_container_name

        # Read files from the bronze container
        bronze_df = spark.read.format("parquet") \
            .option("recursiveFileLookup", "true") \
            .load(f"abfss://{bronze_container_name}@andrewstockmarket.dfs.core.windows.net/")

        # Add a created_date column
        silver_df = bronze_df.withColumn("created_date", current_timestamp()) \
                            .withColumn("symbol", col("meta.symbol"))

        # Write to the silver container (ensure folder_name is defined)
        silver_df.write.format("delta").mode("append") \
            .partitionBy("symbol") \
            .save(f"abfss://{silver_container_name}@andrewstockmarket.dfs.core.windows.net/")




    def silver_to_gold_delta(self, silver_container_name= None, gold_container_name= None ): 

        # Set default values for container names if they are not provided



        if silver_container_name is None:
            silver_container_name = self.silver_container_name

        if gold_container_name is None:
            gold_container_name = self.gold_container_name

        silver_data = spark.read.format("delta").load(f"abfss://{silver_container_name}@{self.storage_account}.dfs.core.windows.net")


        ### Generate Dim Stock ###

        # Transform the DataFrame into the gold table with the corresponding symbol

        dim_stock = silver_data.select(
            col("meta.symbol").alias("symbol"),
            col("meta.interval").alias("interval"),
            col("meta.currency").alias("currency"),
            col("meta.exchange_timezone").alias("exchange_timezone"),
            col("meta.exchange").alias("exchange"),
            col("meta.mic_code").alias("mic_code"),
            col("meta.type").alias("type"),
            col("created_date").cast(TimestampType())
        )

        # Write meta data to the silver Delta table
        dim_stock.write.format("delta") \
            .mode("overwrite") \
            .option("mergeSchema", "true") \
            .partitionBy("symbol") \
            .save(f"abfss://{gold_container_name}@{self.storage_account}.dfs.core.windows.net/dim_stock")



        ### Generate Fact Stock Price ###

        # Explode the 'values' array and add the sid from the corresponding meta row
        fact_stock_price = silver_data.select("symbol","created_date", explode("values").alias("value"))


        # Transform the DataFrame into the gold table with the corresponding symbol
        fact_stock_price = fact_stock_price.select(
            col("symbol") .alias("symbol"),
            col("value.datetime").cast(TimestampType()).alias("datetime"),
            col("value.open").cast(DoubleType()).alias("open"),
            col("value.high").cast(DoubleType()).alias("high"),
            col("value.low").cast(DoubleType()).alias("low"),
            col("value.close").cast(DoubleType()).alias("close"),
            col("value.volume").cast(IntegerType()).alias("volume"),
            col("created_date").cast(TimestampType())
        )


        # Write the values data to the silver Delta table
        fact_stock_price.write.format("delta") \
            .mode("append") \
            .option("mergeSchema", "true") \
            .partitionBy("symbol") \
            .save(f"abfss://{gold_container_name}@{self.storage_account}.dfs.core.windows.net/fact_stock_price")
        


# COMMAND ----------

# Function to install a package if not already installed
def install_package(package_name):
    try:
        # Try importing the package to check if it's already installed
        __import__(package_name)
        print(f"Package '{package_name}' is already installed.")
    except ImportError:
        print(f"Package '{package_name}' not found. Installing now...")
        # Install the package and wait for the installation to complete
        %pip install {package_name}
        # Re-import the package to ensure the installation was successful
        __import__(package_name)
        print(f"Package '{package_name}' has been installed.")

# Specify the package name
package_name = 'websockets'

# Call the function to handle installation
install_package(package_name)


import asyncio
import json
import websockets



# Subscribe to the WebSocket to get prices in real time
async def subscribe_to_websocket():
    # Replace {$route} with the appropriate route (e.g., "price", "timeseries", etc.)
    route = "quotes/price"  # Replace with your route
    api_key = "23c1a7c2da0148c584eac977ac756432"  # Replace with your actual API key
    uri = f"wss://ws.twelvedata.com/v1/{route}?apikey={api_key}"

    async with websockets.connect(uri) as websocket:
        # Create the subscription message
        subscription_message = {
            "action": "subscribe",
            "params": {
                "symbols": "AAPL,INFY,TRP,QQQ,IXIC,EUR/USD,USD/JPY,BTC/USD"
            }
        }

        # Send the subscription message
        await websocket.send(json.dumps(subscription_message))
        print(f"Sent: {subscription_message}")

        # Receive messages from the WebSocket
        while True:
            response = await websocket.recv() 
            response_json = json.loads(response)
            print(f"Received: { json.dumps(response_json, indent=4) }")

# Run the subscription function
# await subscribe_to_websocket()


# COMMAND ----------

import requests
import json
import time

class GetStockData(): 

    def __init__(self, api_key: str):
        self.api_key = api_key

    def get_historical_stock_data(self, interval: str = "1day", symbols: list = ["QQQ", "VOO"], start_date: str = "2021-01-01", end_date: str = "2021-12-31"): 

        interval_allowed_list = ["1min", "1h", "1day", "1week", "1month"]
        if interval not in interval_allowed_list:
            raise ValueError(f"Invalid interval. Allowed intervals are: {', '.join(interval_allowed_list)}")

        responses_list = []
        # Format of date in "yyyy-mm-dd"
        for symbol in symbols:
            time.sleep(7)
            url = f"https://api.twelvedata.com/time_series?symbol={symbol}&interval={interval}&start_date={start_date}&end_date={end_date}&apikey={self.api_key}"
            response = requests.get(url)
            # Check if the request was successful
            if response.status_code == 200:
                # Parse the JSON data
                data = response.json()
                # Check the structure of the JSON response
                if 'meta' in data and data.get('status') == 'ok':
                    print(f"data saved for symbol {symbol} and date range {start_date} to {end_date}.")
                    responses_list.append(data)
                 
                else:
                    print(f"No data found in the JSON response for symbol {symbol} and date range {start_date} to {end_date}.")

        return responses_list


# COMMAND ----------

# MAGIC %md
# MAGIC Source to bronze

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

# MAGIC %md
# MAGIC NBronze to silver

# COMMAND ----------

# Initialize the configuration object
ADLSController = ADLSController(storage_account="andrewstockmarket")

ADLSController.bronze_to_silver_delta()

# COMMAND ----------

# MAGIC %md
# MAGIC Silver to gold

# COMMAND ----------



# COMMAND ----------

# Initialize the configuration object
ADLS_Controller = ADLSController(storage_account="andrewstockmarket")


# COMMAND ----------

ADLS_Controller.silver_to_gold_delta()
