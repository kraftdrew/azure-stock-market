# COMMAND ----------
%run ./Raw_to_Silver.ipynb

# COMMAND ----------
%run ./Dim_Silver_to_Gold.ipynb

# COMMAND ----------
%run ./Fact_Silver_to_Gold.ipynb

# COMMAND ---------- [markdown]
# ### Debug

# COMMAND ----------

# from dev_spark_session import DevSparkSession

# # Initialize Spark with Hive support (so CREATE/DROP TABLE work)
# spark = DevSparkSession().spark

# # Your Delta folder path
# silver_path = "/Users/PC/Desktop/VS Code Repositories/azure-stock-market/Azure storage/Silver/delta-table"
# dimSymbol_path = "/Users/PC/Desktop/VS Code Repositories/azure-stock-market/Azure storage/Gold/delta-tables/dim-symbol"
# dimDate_path = "/Users/PC/Desktop/VS Code Repositories/azure-stock-market/Azure storage/Gold/delta-tables/dim-date"
# fact_path = "/Users/PC/Desktop/VS Code Repositories/azure-stock-market/Azure storage/Gold/delta-tables/fact-daily-summary"


# df_history = spark.sql(f" select  year, count(*)  from  delta.`{dimDate_path}`  group by year order by year  ")


# df_history.show(100, truncate=False)


