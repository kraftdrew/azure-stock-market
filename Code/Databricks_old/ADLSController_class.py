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

# dbutils.secrets.listScopes()
# service_credential = dbutils.secrets.get(scope="use",key="kv-stock-market")

