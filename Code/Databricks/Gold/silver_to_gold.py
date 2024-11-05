# Databricks notebook source
# MAGIC %run "../nb_common"

# COMMAND ----------

# MAGIC %md
# MAGIC ##### **Get** Stock Data from API

# COMMAND ----------

# Initialize the configuration object
ADLS_Controller = ADLSController(storage_account="andrewstockmarket")


# COMMAND ----------

ADLS_Controller.silver_to_gold_delta()

# COMMAND ----------

# %sql 
# select * from gold.fact_stock_price
