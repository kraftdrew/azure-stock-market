# COMMAND ----------


import sys, os
from pyspark.sql.functions import col, explode, monotonically_increasing_id, lit, cast , concat, expr, date_format, sha2, concat_ws
from pyspark.sql.types import DateType, TimestampType   # sha2,concat_ws,trim, lit
from delta.tables import DeltaTable
from datetime import date, timedelta


# COMMAND ----------


# Insert the parent directory (one level up) onto Python’s module search path
sys.path.insert(0, os.path.abspath(".."))

from dev_spark_session import DevSparkSession 
from scd_type2_handler import SCDType2Handler
from python_helper import HelperMethons



# COMMAND ---------- [markdown]
# ### Initiate Spark

# COMMAND ----------

# stockdata = GetStockData() 
spark = DevSparkSession().spark


silver_path = "/Users/PC/Desktop/VS Code Repositories/azure-stock-market/Azure storage/Silver/delta-table"  # Target location for Silver Delta table
dim_symbol_path = "/Users/PC/Desktop/VS Code Repositories/azure-stock-market/Azure storage/Gold/delta-tables/dim-symbol"
fact_daily_path = "/Users/PC/Desktop/VS Code Repositories/azure-stock-market/Azure storage/Gold/delta-tables/fact-daily-summary"



# COMMAND ----------

# silver_path = "/Users/PC/Desktop/VS Code Repositories/azure-stock-market/Azure storage/Silver/delta-table"  # Target location for Silver Delta table

# df_silver = spark.read.format("delta").load(silver_path)

# df_silver.createOrReplaceTempView("stemp")

# spark.sql("select * from stemp").limit(2).show()


# silver_df = spark.read.format("delta").load(silver_path)

# spark.sql( f"delete from delta.`{silver_path}` where __Hashkey like '%c%' ") 

# COMMAND ---------- [markdown]
# ## Dim Symbol

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
df_history = spark.sql(f" select *  from  delta.`{dim_symbol_path}`  ")
df_history = spark.sql(f" delete   from  delta.`{fact_daily_path}`  ")
# df_history = spark.sql(f" delete   from  delta.`{dim_symbol_path}`  ")

  
df_history.show(truncate=False)

# COMMAND ---------- [markdown]
# ## Fact Trading

# COMMAND ----------
df_silver = spark.read.format("delta").load(silver_path)
df_fact =  df_silver # .select("Volume","High","Low", "Close", "Open","Date")
df_fact =  df_fact.withColumn("DateID", date_format(col("Date"), "yyyyMMdd").cast("int")).drop("Date")


# Add Hash Key for Dim Symbol 

businessColumns  = ["Symbol", "ExchangeName", "Currency"] 

df_fact = df_fact.withColumn("DimSymbolBusinessHash" , sha2( concat_ws("|", *businessColumns), 256))



df_dim_symbol = spark.table(f"delta.`{dim_symbol_path}` ")

df_fact = df_fact.alias("f").join(df_dim_symbol.alias("d"), on = expr("f.DimSymbolBusinessHash = d.__BusinessKeyHash"), how = "left" ) \
                .where("d.__CurrentFlag = true") \
                .selectExpr("d.SymbolSID", 
                            "f.Volume", 
                            "f.High",
                            "f.Low",
                            "f.Open",
                            "f.Close",
                            "f.DateID"
                )



parameters = {
        "businessColumns" : "Symbol,ExchangeName,Currency",
        "typeIColumns" : "", 
        "tableType" : "Fact"
        }

scd2Handler =  SCDType2Handler(parameters)


scd2Handler.refresh_timestamp()
add_audit_columns =  scd2Handler.add_audit_columns
df_fact = df_fact.transform(add_audit_columns)


## ADD_SID

sid_offest = spark.read.format("delta").load(fact_daily_path)

sid_offest = sid_offest.selectExpr("max(TransactionSID)").head()[0]
sid_offest = sid_offest + 1 if sid_offest else 0



df_fact = df_fact.withColumn("TransactionSID", monotonically_increasing_id() +  sid_offest)



df_fact.show()

deltaTable = DeltaTable.forPath(spark, fact_daily_path)

scd2Handler.delta_merge_typeII(deltaTable, df_fact)




# COMMAND ----------
df_history = spark.sql(f" select count(*)  from  delta.`{fact_daily_path}`  ")

# df_history = spark.sql(f" delete   from  delta.`{fact_daily_path}`  ")

  
df_history.show(truncate=False)

# COMMAND ----------


parameters = {
        "businessColumns" : "Symbol,ExchangeName,Currency",
        "typeIColumns" : "", 
        "tableType" : "Dim"
        }
scd2Handler =  SCDType2Handler(parameters)



silver_path = "/Users/PC/Desktop/VS Code Repositories/azure-stock-market/Azure storage/Silver/delta-table"  # Target location for Silver Delta table

df_silver = spark.read.format("delta").load(silver_path)

df_dimSymbol =  df_silver.select("Symbol","ExchangeName","Currency", "Type", "ExchangeTimeZone").distinct()

dim_symbol_path = "/Users/PC/Desktop/VS Code Repositories/azure-stock-market/Azure storage/Gold/delta-tables/dim-symbol"



scd2Handler.refresh_timestamp()

# df_dimSymbol = df_dimSymbol.withColumn("Type", concat(col("Type"), lit("_test") ) )

add_audit_columns =  scd2Handler.add_audit_columns
df_dimSymbol = df_dimSymbol.transform(add_audit_columns)



sid_offest = spark.read.format("delta").load(dim_symbol_path)


sid_offest = sid_offest.selectExpr("max(Symbol_SID)").head()[0]

sid_offest = sid_offest + 1 if sid_offest else 0



df_dimSymbol = df_dimSymbol.withColumn("Symbol_SID", monotonically_increasing_id() +  sid_offest)

spark.read.format("delta").load(dim_symbol_path).show()

df_dimSymbol.show(truncate=False)
deltaTable = DeltaTable.forPath(spark, dim_symbol_path)
scd2Handler.delta_merge_typeII(deltaTable, df_dimSymbol)




# COMMAND ----------
from pyspark.sql.functions import sequence, to_date, explode, year, month, dayofmonth, expr, date_format, dayofweek, lit
from delta.tables import DeltaTable


# COMMAND ----------



start_date = date.fromisoformat('2000-01-01')
end_date = date.fromisoformat('2010-01-01')


    # 1. Build a 1‑row DataFrame just so we can call sequence(…)
bounds = spark.range(1).withColumn("dates_list", sequence( lit(start_date), lit(end_date), expr("interval 1 day")))

bounds.show(truncate=False)

# COMMAND ---------- [markdown]
# ## Populate Dim Table if needed

# COMMAND ----------


hm = HelperMethons(spark=spark)
dimDate_folder =  "/Users/PC/Desktop/VS Code Repositories/azure-stock-market/Azure storage/Gold/delta-tables/dim-date"
df_dimdate = spark.read.format("delta").load(dimDate_folder)


max_date_dimDate =  df_dimdate.selectExpr(" cast(max(date) as date) as max_date").head()[0]
min_date_silver =  df_silver.selectExpr(" cast(min(date) as date) as min_date").head()[0]
max_date_silver =  df_silver.selectExpr(" cast(max(date) as date) as max_date").head()[0]



## populate DimDate table if we dont have records with dates 
if min_date_silver > max_date_dimDate:
    
    start_date = max_date_dimDate + timedelta(days=1)
    end_date =  date( max_date_silver.year , 12, 31)
    
    hm.update_DimDate_fromRange(start_date, end_date )
    print(f"Dim Table Updated with date range [ {start_date} : {end_date} ] ")
    
    
df_dimdate = spark.read.format("delta").load(dimDate_folder)




# COMMAND ----------


  



# COMMAND ----------

df.head(5)

# COMMAND ----------


# COMMAND ----------


# COMMAND ----------


# COMMAND ---------- [markdown]
# ### Get Data from API

# COMMAND ---------- [markdown]
# ### Bronze -> Silver


