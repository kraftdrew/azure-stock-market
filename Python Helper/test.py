typeIColumnsList = ['col1', 'col2', 'col3', 'col4']

 


update_set = { 
                        
                        "__UpdatedBatchLogId" : "lit(self.batch_id)",
                        "__UpdateDateTime" : "current_timestamp() "
                        }
                        
for col in typeIColumnsList: 
    update_set[col] = f"s.{col}"
    
    
print(update_set) 
    