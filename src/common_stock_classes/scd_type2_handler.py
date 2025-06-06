import datetime as dt
from pyspark.sql.functions import current_timestamp, sha2, concat_ws, lit, col
from pyspark.sql.types import TimestampType
import uuid





class SCDType2Handler:
    
    def __init__(self, parameters):
        
        self.unpack_params(parameters)
        self.batch_id = str(uuid.uuid4()) 
        self.audit_columns =   {
            "__ActivationDateTime", "__BusinessKeyHash", "__CreateDateTime", "__CreatedBatchLogId", "__CurrentFlag",
            "__DeactivationDateTime", "__DeletedFlag", "__EffectiveEndDateTime", "__EffectiveStartDateTime",
            "__FactKeyHash", "__Hash1Type", "__Hash2Type", "__HashKey", "__HashValue", "__LastModified", "__lastmodified",
            "__UpdateDateTime", "__UpdatedBatchLogId"
        }
        self.businessColumnsList   = [col.strip()  for col in self.businessColumns.split(",") if  col !=  ""]
        self.typeIColumnsList = [col.strip()  for col in self.typeIColumns.split(",") if  col !=  ""]
        self.effectiveStartDateTime = dt.datetime.now()
        self.effectiveEndDateTime = self.effectiveStartDateTime - dt.timedelta(seconds=1)
        

    def unpack_params(self, params):
        """
        Extract the necessary parameters from the dictionary and store them
        as attributes on this class. Raise an error if any required key is missing.
        """
        
        try:
            self.businessColumns = params["businessColumns"]
            self.typeIColumns = params["typeIColumns"]
            self.tableType = params["tableType"]

        except KeyError as missing_key:
            raise ValueError(f"Missing required parameter: {missing_key}")
        
        if self.tableType not in ("Stage", "Dim", "Fact"):
            raise ValueError(f"tableType value [{self.tableType!r}] is not in allowed list ['Stage', 'Dim', 'Fact']")
            
    
    
    def refresh_timestamp(self):
        
        self.effectiveStartDateTime = dt.datetime.now()
        self.effectiveEndDateTime = self.effectiveStartDateTime - dt.timedelta(seconds=1)
        


    def add_audit_columns(self, df):
        
        
        if  self.tableType == "Dim":
            
    
            Hash2Type = sorted(list({col for col in df.columns}  - self.audit_columns  -  set(self.typeIColumnsList)))
            
            # Assume df is your source DataFrame and columns like business_key and some_column are present.
            df = df.withColumn("__CurrentFlag", lit(True)) \
                .withColumn("__DeletedFlag", lit(False)) \
                .withColumn("__EffectiveStartDateTime",  lit(self.effectiveStartDateTime)  )\
                .withColumn("__EffectiveEndDateTime", lit('2099-12-31').cast(TimestampType()) ) \
                .withColumn("__BusinessKeyHash", sha2(concat_ws("|", *self.businessColumnsList), 256)) \
                .withColumn("__Hash1Type", sha2(concat_ws("|", *self.typeIColumnsList ), 256)) \
                .withColumn("__Hash2Type", sha2(concat_ws("|", *Hash2Type ), 256)) \
                .withColumn("__CreatedBatchLogId", lit(self.batch_id)) \
                .withColumn("__CreateDateTime", current_timestamp()) \
                .withColumn("__UpdatedBatchLogId", lit(None)) \
                .withColumn("__UpdateDateTime", lit(None))
               
                
        elif self.tableType == "Fact":
            

            FactSCD1Hash = sorted(list(set(self.typeIColumnsList)))

            
            # Assume df is your source DataFrame and columns like business_key and some_column are present.
            df = df.withColumn("__DeletedFlag", lit(False)) \
                .withColumn("__FactKeyHash", sha2(concat_ws("|", *self.businessColumnsList), 256)) \
                .withColumn("__FactSCD1Hash", sha2(concat_ws("|", *FactSCD1Hash ), 256)) \
                .withColumn("__CreatedBatchLogId", lit(self.batch_id)) \
                .withColumn("__CreateDateTime", current_timestamp()) \
            
        ## silver, stage
        else:
            
            hashValueColumns = sorted(list({col for col in df.columns}  - self.audit_columns  -  set(self.typeIColumnsList)))
            
            # Assume df is your source DataFrame and columns like business_key and some_column are present.
            df = df.withColumn("__CurrentFlag", lit(True)) \
                .withColumn("__DeletedFlag", lit(False)) \
                .withColumn("__EffectiveStartDateTime",  lit(self.effectiveStartDateTime)  )\
                .withColumn("__EffectiveEndDateTime", lit('2099-12-31').cast(TimestampType()) ) \
                .withColumn("__lastmodified", current_timestamp()) \
                .withColumn("__HashKey", sha2(concat_ws("|", *self.businessColumnsList), 256)) \
                .withColumn("__HashValue", sha2(concat_ws("|", *hashValueColumns ), 256)) \
                .withColumn("__CreatedBatchLogId", lit(self.batch_id)) \
                .withColumn("__CreateDateTime", current_timestamp()) \
                .withColumn("__UpdatedBatchLogId", lit(None)) \
                .withColumn("__UpdateDateTime", lit(None))
            
        return df
    

    def delta_merge_typeII(self, target_delta_table, source_df):


      
        
        # Load the Silver table as a DeltaTable object

        
 
        if  self.tableType == "Dim":
            
            # expire rows  
            
            if self.typeIColumnsList:
            
            
                update_set = { 
                        **{column : col(f"s.{column}") for column in  self.typeIColumnsList },
                        "__UpdatedBatchLogId" : lit(self.batch_id),
                        "__UpdateDateTime" : current_timestamp() 
                        }
                
             

            
                ##Type1 Column
                target_delta_table.alias("t").merge(
                    source = source_df.alias("s"),
                    condition = """ t.__BusinessKeyHash = s.__BusinessKeyHash
                                    AND t.__Hash1Type <> s.__Hash1Type
                                    AND t.__CurrentFlag = True
                                """
                ).whenMatchedUpdate(
                    set = update_set          
                ).execute()
                
            
            ##Type2 Column
            target_delta_table.alias("t").merge(
                source = source_df.alias("s"),
                condition = """ t.__BusinessKeyHash = s.__BusinessKeyHash
                                AND t.__Hash2Type <> s.__Hash2Type
                                AND t.__CurrentFlag = True
                            """
            ).whenMatchedUpdate(
                set = {
                    "__CurrentFlag": "false",
                    "__DeletedFlag": "false",
                    "__UpdatedBatchLogId" : lit(self.batch_id),
                    "__UpdateDateTime" : "current_timestamp()",
                    "__EffectiveEndDateTime": f"cast('{self.effectiveEndDateTime.strftime('%Y-%m-%d %H:%M:%S')}' as timestamp)",                
                }).execute()

            target_delta_table.alias("t").merge(
                source_df.alias("s"),
                condition = """
                            t.__BusinessKeyHash = s.__BusinessKeyHash
                            AND t.__CurrentFlag = True
                            """ 
            ).whenNotMatchedInsertAll().execute()
        
        
        elif  self.tableType == "Fact":
            

            (target_delta_table.alias("t")
            .merge(
                source_df.alias("s"),
                # Match on the business key only
                "t.__FactKeyHash = s.__FactKeyHash"
            )
            # 1) If the keys match but the hash changed, delete the stale row
            .whenMatchedDelete(
                condition="t.__FactSCD1Hash <> s.__FactSCD1Hash"
            )
            # 2) If a target row has no corresponding source row, delete it
            .whenNotMatchedBySourceDelete()
            # 3) If a source row has no matching target, insert it
            .whenNotMatchedInsertAll()
            .execute()
            )


        else: 
              
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
                "__UpdatedBatchLogId" : lit(self.batch_id),
                "__UpdateDateTime" : "current_timestamp()",
                "__EffectiveEndDateTime": f"cast('{self.effectiveEndDateTime.strftime('%Y-%m-%d %H:%M:%S')}' as timestamp)",
                "__lastmodified": "current_timestamp()",
            
            }).execute()
        


            target_delta_table.alias("t").merge(
                source_df.alias("s"),
                condition = """
                            t.__HashKey = s.__HashKey
                            AND t.__CurrentFlag = True
                            """ 
            ).whenNotMatchedInsertAll().execute()
        


