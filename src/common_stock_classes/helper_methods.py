from pyspark.sql.functions import explode, lit, col, sequence, date_format, dayofweek, year, expr
from datetime import date
from delta.tables import DeltaTable



class HelperMethods(): 
    
    def __init__(self, spark):
        
        self.spark = spark
         

    def update_DimDate_fromRange(self, dimDate_path : str,  start_date: str =  '2000-01-01', 
                    end_date: str = '2010-12-31'
                    ): 
        
        

        if isinstance(start_date, str): 
            start_date = date.fromisoformat(start_date)
            
        if isinstance(end_date, str):
            end_date = date.fromisoformat(end_date)



        # 1. Build a 1‑row DataFrame just so we can call sequence(…)
        bounds = self.spark.range(1).withColumn("dates_list", sequence(lit(start_date), lit(end_date), expr("interval 1 day")))


        date_df =  ( bounds.select(
                    explode(col("dates_list")).alias("date"))
                        .withColumn("Date", col("date").cast("date"))
                        .withColumn("DateID", date_format(col("date"), "yyyyMMdd").cast("int"))
                        .withColumn("Day", date_format(col("date"), "dd").cast("int") )
                        .withColumn("DayOfWeek", date_format(col("date"), "EEEE"))
                        .withColumn("DayOfWeekNumber", dayofweek("date"))
                        .withColumn("MonthName", date_format(col("date"), "MMM"))
                        .withColumn("MonthNumber", date_format(col("date"), "M").cast("int"))
                        .withColumn("Year", year("date").cast("int"))
                        .withColumn("YearMonth", date_format(col("date"), "yyyyMM").cast("int"))
        )


        if not DeltaTable.isDeltaTable(self.spark, dimDate_path):
            
            date_df.write\
                .format("delta")\
                .mode("overwrite")\
                .save(dimDate_path)
        else:
            
            t_df = DeltaTable.forPath(self.spark, dimDate_path)
            
            t_df.alias('t') \
            .merge(condition="t.date = s.date",
                source = date_df.alias("s") ) \
            .whenNotMatchedInsertAll() \
            .execute()
            print(f"Dim Table Updated with date range [ {start_date} : {end_date} ] ")




