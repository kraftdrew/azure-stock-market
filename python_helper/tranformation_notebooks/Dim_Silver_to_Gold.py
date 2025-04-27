# COMMAND ----------
import sys, os
from pyspark.sql.functions import  monotonically_increasing_id
from delta.tables import DeltaTable

# Insert the parent directory (one level up) onto Python’s module search path
sys.path.insert(0, os.path.abspath(".."))

from dev_spark_session import DevSparkSession 
from scd_type2_handler import SCDType2Handler


# COMMAND ---------- [markdown]
# ### Initiate Spark

# COMMAND ----------

# stockdata = GetStockData() 
spark = DevSparkSession().spark


silver_path = "/Users/PC/Desktop/VS Code Repositories/azure-stock-market/Azure storage/Silver/delta-table"  # Target location for Silver Delta table
dim_symbol_path = "/Users/PC/Desktop/VS Code Repositories/azure-stock-market/Azure storage/Gold/delta-tables/dim-symbol"
fact_daily_path = "/Users/PC/Desktop/VS Code Repositories/azure-stock-market/Azure storage/Gold/delta-tables/fact-daily-summary"



# COMMAND ---------- [markdown]
# ## Dim Symbol Loader

# COMMAND ----------


parameters = {
        "businessColumns" : "Symbol,ExchangeName,Currency",
        "typeIColumns" : "", 
        "tableType" : "Dim"
        }
scd2Handler =  SCDType2Handler(parameters)



df_silver = spark.read.format("delta").load(silver_path)
df_dimSymbol =  df_silver.select("Symbol","ExchangeName","Currency", "Type", "ExchangeTimeZone").distinct()
scd2Handler.refresh_timestamp()

# df_dimSymbol = df_dimSymbol.withColumn("Type", concat(col("Type"), lit("_test") ) )

add_audit_columns =  scd2Handler.add_audit_columns
df_dimSymbol = df_dimSymbol.transform(add_audit_columns)
sid_offest = spark.read.format("delta").load(dim_symbol_path)
sid_offest = sid_offest.selectExpr("max(SymbolSID)").head()[0]
sid_offest = sid_offest + 1 if sid_offest else 0



df_dimSymbol = df_dimSymbol.withColumn("SymbolSID", monotonically_increasing_id() +  sid_offest)
spark.read.format("delta").load(dim_symbol_path).show()
df_dimSymbol.show(truncate=False)
deltaTable = DeltaTable.forPath(spark, dim_symbol_path)
scd2Handler.delta_merge_typeII(deltaTable, df_dimSymbol)


# COMMAND ----------
# df_history = spark.sql(f" select *  from  delta.`{dim_symbol_path}`  ")

  
# df_history.show(truncate=False)


