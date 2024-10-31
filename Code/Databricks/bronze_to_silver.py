# Databricks notebook source
# MAGIC
# MAGIC %run "/Workspace/Users/andrewkravchuk@outlook.com/dev/nb_common"

# COMMAND ----------

# MAGIC %md
# MAGIC ##### **Get** Stock Data from API

# COMMAND ----------

# Initialize the configuration object
ADLSController = ADLSController(storage_account="andrewstockmarket")



# COMMAND ----------

ADLSController.bronze_to_silver_delta()

# COMMAND ----------

# df = spark.read.format("delta").load("abfss://silver@andrewstockmarket.dfs.core.windows.net")
# display(df)
