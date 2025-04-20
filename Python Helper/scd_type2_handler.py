import datetime
from pyspark.sql.functions import current_timestamp, sha2, concat_ws, lit, cast
from pyspark.sql.types import DateType, TimestampType
from pyspark.sql.dataframe import DataFrame




class SCDType2Handler:
    
    def __init__(self, parameters):
        
        self.unpack_params(parameters)
        
        self.audit_columns =   {
            "__ActivationDateTime", "__BusinessKeyHash", "__CreateDateTime", "__CreatedBatchLogId", "__CurrentFlag",
            "__DeactivationDateTime", "__DeletedFlag", "__EffectiveEndDateTime", "__EffectiveStartDateTime",
            "__FactKeyHash", "__Hash1Type", "__Hash2Type", "__HashKey", "__HashValue", "__LastModified",
            "__UpdateDateTime", "__UpdatedBatchLogId"
        }
        self.businessColumnsList   = [col.strip()  for col in self.businessColumns.split(",") if  col !=  ""]
        self.typeIColumnsList = [col.strip()  for col in self.typeIColumns.split(",") if  col !=  ""]
        self.activationDateTime = datetime.datetime.now()
        self.deactivationDateTime = self.activationDateTime - datetime.timedelta(seconds=1)
        

    def unpack_params(self, params):
        """
        Extract the necessary parameters from the dictionary and store them
        as attributes on this class. Raise an error if any required key is missing.
        """
        
        try:
            self.businessColumns = params["businessColumns"]
            self.typeIColumns = params["typeIColumns"]

        except KeyError as missing_key:
            raise ValueError(f"Missing required parameter: {missing_key}")
            
    
    
    def refresh_timestamp(self):
        
        self.activationDateTime = datetime.datetime.now()
        self.deactivationDateTime = self.activationDateTime - datetime.timedelta(seconds=1)
        


    def add_audit_columns(self, df):
        
        
        hashValueColumns = sorted(list({col for col in df.columns}  - self.audit_columns  -  set(self.typeIColumnsList)))
        

        
        # Assume df is your source DataFrame and columns like business_key and some_column are present.
        df = df.withColumn("__CurrentFlag", lit(True)) \
            .withColumn("__DeletedFlag", lit(False)) \
            .withColumn("__ActivationDateTime",  lit(self.activationDateTime)  )\
            .withColumn("__DeactivationDateTime", lit('2099-12-31').cast(TimestampType()) ) \
            .withColumn("__lastmodified", current_timestamp()) \
            .withColumn("__HashKey", sha2(concat_ws("|", *self.businessColumnsList), 256)) \
            .withColumn("__HashValue", sha2(concat_ws("|", *hashValueColumns ), 256))
        
        return df

    def delta_merge_typeII(self, target_delta_table, source_df):
      
        # Load the Silver table as a DeltaTable object

        # expire rows 
        target_delta_table.alias("t").merge(
            source = source_df.alias("s"),
            condition = """ t.__HashKey = s.__HashKey
                            AND t.__HashValue <> s.__HashValue
                            AND t.__CurrentFlag = True
                        """
        ).whenMatchedUpdate(
            set = {
                "__CurrentFlag": "false",
                "__DeletedFlag": "false",
                "__DeactivationDateTime": f"cast('{self.deactivationDateTime.strftime('%Y-%m-%d %H:%M:%S')}' as timestamp)",
                "__lastmodified": "current_timestamp()",
            
            }).execute()


        target_delta_table.alias("t").merge(
            source_df.alias("s"),
            condition = """
                        t.__HashKey = s.__HashKey
                        AND t.__CurrentFlag = True
                        """ 
        ).whenNotMatchedInsertAll().execute()
    


