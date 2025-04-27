# COMMAND ----------


import sys, os
from pyspark.sql.functions import col, explode # lit, cast  
from pyspark.sql.types import DateType, TimestampType   # sha2,concat_ws,trim, lit

# Insert the parent directory (one level up) onto Python’s module search path
sys.path.insert(0, os.path.abspath(".."))

from dev_spark_session import DevSparkSession 
from get_stock_data import GetStockData
from scd_type2_handler import SCDType2Handler
from delta.tables import DeltaTable



# COMMAND ---------- [markdown]
# ### Initiate Spark

# COMMAND ----------


stockdata = GetStockData() 
spark = DevSparkSession().spark

# Paths for Bronze and Silver data
bronze_path = "/Users/PC/Desktop/VS Code Repositories/azure-stock-market/Azure storage/Bronze"  # Bronze data stored in Parquet or Delta
silver_path = "/Users/PC/Desktop/VS Code Repositories/azure-stock-market/Azure storage/Silver/delta-table"  # Target location for Silver Delta table



# COMMAND ---------- [markdown]
# ### Get Data from API

# COMMAND ----------
json_data  = stockdata.get_historical_stock_data()

df = spark.createDataFrame(json_data) 
df = df.withColumn("symbol", col("meta").symbol).filter( col("status") == "ok" ).drop(df.status)
# df.show(truncate = False)


df.write \
    .format("parquet") \
    .mode("overwrite") \
    .partitionBy( "symbol" ) \
    .save("/Users/PC/Desktop/VS Code Repositories/azure-stock-market/Azure storage/Bronze")



# COMMAND ---------- [markdown]
# ### Bronze -> Silver

# COMMAND ----------



### Tranformt Bronze -> Silver

df_bronze = spark.read.load(bronze_path).drop("symbol")

df_bronze = df_bronze.withColumn( "values", explode("values") )

df_bronze = df_bronze.select(
    col("meta").getItem("symbol").alias("Symbol"),
    col("meta").getItem("exchange").alias("ExchangeName"),
    col("meta").getItem("currency").alias("Currency"),
    col("meta").getItem("type").alias("Type"),
    col("meta").getItem("exchange_timezone").alias("ExchangeTimeZone"),
    col("values").getItem("volume").alias("Volume"),
    col("values").getItem("high").alias("High"),
    col("values").getItem("low").alias("Low"),
    col("values").getItem("close").alias("Close"),
    col("values").getItem("open").alias("Open"),
    col("values").getItem("datetime").alias("Date"))

df_bronze = df_bronze.dropDuplicates()


# df_bronze.show()


# COMMAND ----------


parameters = {
        "businessColumns" : "Symbol,ExchangeName,Currency,Date",
        "typeIColumns" : "",
        "tableType" : "Stage"
        }

scd2Handler =  SCDType2Handler(parameters)
scd2Handler.refresh_timestamp()
add_audit_columns =  scd2Handler.add_audit_columns

df_bronze = df_bronze.transform(add_audit_columns)


df_bronze.show(truncate=False)
deltaTable = DeltaTable.forPath(spark, silver_path)
scd2Handler.delta_merge_typeII(deltaTable, df_bronze)

# COMMAND ----------


# df_history = spark.sql(f" select count(*) from  delta.`{silver_path}`  ")
  
# df_history.show()




