from pyspark.sql import SparkSession 




spark = SparkSession.builder.getOrCreate()


df = spark.createDataFrame(
    [("Andrew", 26),
    ("Vlad", 25)], 
    ["Name", "Age"] 
)




df.show()
