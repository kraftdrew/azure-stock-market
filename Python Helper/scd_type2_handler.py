import datetime
from delta.tables import DeltaTable
from pyspark import SparkContext
from pyspark.sql.functions import current_timestamp, sha2, concat_ws, lit
from pyspark.sql.dataframe import DataFrame


parameters = {
        "businessColumns" : "Symbol,ExchangeName,Currency,Date",
        "typeIColumns" : "Symbol",
        "source_path" : "/Users/PC/Desktop/VS Code Repositories/azure-stock-market/Azure storage/Bronze",
        "target_path" :  "/Users/PC/Desktop/VS Code Repositories/azure-stock-market/Azure storage/Silver/delta-table" }


class SCDType2Handler:
    
    def __init__(self, spark : SparkContext, parameters ):
        
        self.spark = spark
        self.audit_columns =   {
            "__ActivationDateTime", "__BusinessKeyHash", "__CreateDateTime", "__CreatedBatchLogId", "__CurrentFlag",
            "__DeactivationDateTime", "__DeletedFlag", "__EffectiveEndDateTime", "__EffectiveStartDateTime",
            "__FactKeyHash", "__Hash1Type", "__Hash2Type", "__HashKey", "__HashValue", "__LastModified",
            "__UpdateDateTime", "__UpdatedBatchLogId"
        }
        self.businessColumnsList   = [col.strip()  for col in self.businessColumns.split(",") if  col !=  ""]
        self.typeIColumnsList = [col.strip()  for col in self.TypeIColumns.split(",") if  col !=  ""]
        self.typeIColumnsList = list({col for col in  df_bronze.columns}  - self.audit_columns  -  set(self.typeIColumnsList)).sort()
        self.unpack_params(parameters)


    def unpack_params(self, params):
        """
        Extract the necessary parameters from the dictionary and store them
        as attributes on this class. Raise an error if any required key is missing.
        """
        
        try:
            self.businessColumns = params["businessColumns"]
            self.typeIColumns = params["typeIColumns"]
            self.source_path = params["source_path"]
            self.target_path = params["target_path"]
            
        except KeyError as missing_key:
            raise ValueError(f"Missing required parameter: {missing_key}")
            
    
    
    def load_delta_to_df(self, load_path) -> DataFrame: 
        
        df = self.spark.read.format("delta").load(load_path)
        return df
    
    
    def get_deactivationDateTime(self):
        
        activationDateTime = datetime.datetime.now()
        deactivationDateTime = activationDateTime - datetime.timedelta(seconds=1)
        return  activationDateTime, deactivationDateTime
        


    def add_audit_columns(self, dataframe):
        
        
        
        # Assume df is your source DataFrame and columns like business_key and some_column are present.
        dataframe = dataframe.withColumn("__CurrentFlag", lit(True)) \
            .withColumn("__DeletedFlag", lit(False)) \
            .withColumn("__ActivationDateTime",  lit(activationDateTime)  ) \
            .withColumn("__DeactivationDateTime", lit(None) ) \
            .withColumn("__lastmodified", current_timestamp()) \
            .withColumn("__HashKey", sha2(concat_ws("|", *self.businessColumnsList), 256)) \
            .withColumn("__HashValue", sha2(concat_ws("|", *self.df_bronze.columns ), 256))
        
        return dataframe

    def delta_merge_typeII(self, target_path = None, source_path = None):
        
        source_path = source_path if source_path else self.source_path
        target_path = target_path if target_path else self.target_path
        

        # Load the Silver table as a DeltaTable object
        deltaTable = DeltaTable.forPath(self.spark, source_path)

        source_df = self.load_delta_to_df(source_path)

        # expire rows 
        deltaTable.alias("t").merge(
            source = source_df.alias("s"),
            condition = """ t.__HashKey = s.__HashKey
                            AND t.__HashValue <> s.__HashValue
                            AND t.__CurrentFlag = True
                        """
        ).whenMatchedUpdate(
            set = {
                "__CurrentFlag": "false",
                "__DeletedFlag": "false",
                "__DeactivationDateTime": f"cast('{deactivationDateTime.strftime('%Y-%m-%d %H:%M:%S')}' as timestamp)",
                "__lastmodified": "current_timestamp()",
            
            }).execute()


        silverDeltaTable.alias("t").merge(
            df_bronze.alias("s"),
            condition = """
                        t.__HashKey = s.__HashKey
                        AND t.__CurrentFlag = True
                        """ 
        ).whenNotMatchedInsertAll().execute()
    
    

