import os
from pyspark.sql import SparkSession
from delta import *

class DevSparkSession:
    
    def __init__(self, appname: str = "SparkDev"):
        
        self.appname = appname

        # Set the local IP to avoid loopback hostname warnings
        os.environ["SPARK_LOCAL_IP"] = "10.0.0.131"

        # Compute the absolute path to the log4j.properties file
        log4j_path = os.path.abspath("log4j.properties")
        # Replace spaces with %20 so that Java can correctly interpret the file path
        log4j_path = log4j_path.replace(" ", "%20")

        # print("Using log4j.properties path:", log4j_path)

        self.spark = configure_spark_with_delta_pip(SparkSession.builder \
            .appName(self.appname) \
            .master("local[*]") \
            .config("spark.driver.host", "10.0.0.131") \
            .config("spark.driver.extraJavaOptions", f"-Dlog4j.configuration=file://{log4j_path}") \
            .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
            .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")) \
            .getOrCreate() 
            
            
    

            
# spark = DevSparkSession().spark
# from delta.tables import DeltaTable



