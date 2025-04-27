# COMMAND ----------
import sys, os
from pyspark.sql.functions import col, monotonically_increasing_id, expr, date_format, sha2, concat_ws
from delta.tables import DeltaTable
from datetime import date, timedelta


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
dim_date_path = "/Users/PC/Desktop/VS Code Repositories/azure-stock-market/Azure storage/Gold/delta-tables/dim-date"
fact_daily_path = "/Users/PC/Desktop/VS Code Repositories/azure-stock-market/Azure storage/Gold/delta-tables/fact-daily-summary"



# COMMAND ---------- [markdown]
# ## Fact Trading Loader

# COMMAND ----------
df_silver = spark.read.format("delta").load(silver_path)
df_fact =  df_silver
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
# df_history = spark.sql(f" select   year , count(*)  from  delta.`{dim_date_path}` group by year   order by year asc ")


# df_history.show(100, truncate=False)

# COMMAND ---------- [markdown]
# ## Populate Dim Table if needed

# COMMAND ----------


hm = HelperMethons(spark=spark)
df_dimdate = spark.read.format("delta").load(dim_date_path)  


df_fact_daily = spark.read.format("delta").load(fact_daily_path)  



max_date_dimDate =  df_dimdate.selectExpr("cast(max(date) as date) as min_date").head()[0]
min_date_fact =  df_fact_daily.selectExpr("to_date(cast(min(DateID) as string), 'yyyyMMdd') as min_date").head()[0]
max_date_fact =  df_fact_daily.selectExpr("to_date(cast(max(DateID) as string), 'yyyyMMdd') as max_date").head()[0]

print(max_date_dimDate,min_date_fact, max_date_fact)

## populate DimDate table if we dont have records with dates 
if min_date_fact > max_date_dimDate: 
    
    print("work")
    
    start_date = max_date_dimDate + timedelta(days=1)
    end_date =  date( max_date_fact.year , 12, 31)
    
    hm.update_DimDate_fromRange(start_date, end_date )
    print(f"Dim Table Updated with date range [ {start_date} : {end_date} ] ")
    
    





