# Architecture Overview

This project demonstrates an end-to-end ELT (Extract, Load, Transform) pipeline based on the Medallion Architecture. The pipeline is designed to handle large-scale data from a data lake, implementing the Bronze, Silver, and Gold layers for structured data processing. This architecture facilitates data quality management, traceability, and scalability for analytical and reporting purposes.

![architecture](/assets/architecture_gif.gif)

## Stages

The pipeline consists of the following main stages:

1. **Bronze Layer (Raw Data)**
    
    We use the TwelveData API as the data source. [API Documentation](https://twelvedata.com/docs#getting-started)
    
    Below is a sample class for fetching data from the API:
```
import requests
import json
import time

class GetStockData(): 

    def __init__(self, api_key: str):
        self.api_key = api_key

    def get_historical_stock_data(self, interval: str = "1day", symbols: list = ["QQQ", "VOO"], start_date: str = "2021-01-01", end_date: str = "2021-12-31"): 

        interval_allowed_list = ["1min", "1h", "1day", "1week", "1month"]
        if interval not in interval_allowed_list:
            raise ValueError(f"Invalid interval. Allowed intervals are: {', '.join(interval_allowed_list)}")

        responses_list = []
        # Format of date in "yyyy-mm-dd"
        for symbol in symbols:
            time.sleep(7)
            url = f"https://api.twelvedata.com/time_series?symbol={symbol}&interval={interval}&start_date={start_date}&end_date={end_date}&apikey={self.api_key}"
            response = requests.get(url)
            # Check if the request was successful
            if response.status_code == 200:
                # Parse the JSON data
                data = response.json()
                # Check the structure of the JSON response
                if 'meta' in data and data.get('status') == 'ok':
                    print(f"data saved for symbol {symbol} and date range {start_date} to {end_date}.")
                    responses_list.append(data)
                 
                else:
                    print(f"No data found in the JSON response for symbol {symbol} and date range {start_date} to {end_date}.")

        return responses_list
```

- This layer stores the raw, unprocessed data from the API.
- Data is saved in a Databricks table, retaining the original format for traceability.
- Minimal processing is performed here, focusing on data ingestion and basic structuring.
1. **Silver Layer (Transformed Data)**
    - Data from the Bronze layer is cleaned, transformed, and structured for analytical processing.
    - Transformations may include removing duplicates, handling missing values, and applying necessary business rules.
    - Processed data is stored in a structured format, making it ready for further enrichment.
2. **Gold Layer (Aggregated Data)**
    - Data in the Silver layer undergoes additional transformations and aggregations based on specific reporting and analytics requirements.
    - This layer is optimized for high-performance queries, particularly for SQL Serverless Compute.
    - Gold layer data serves as the final, enriched dataset used for reporting.
3. **SQL Serverless Compute**
    - Gold layer data is accessed via SQL Serverless, allowing for cost-efficient querying.
    - This stage facilitates integration with the Power BI Service for visual analytics.
4. **Power BI Service**
    - Power BI connects to the SQL Serverless endpoint to generate reports and dashboards.
    - Scheduled data refreshes keep the reports up-to-date with the latest Gold layer data.

### Tech Stack

- Databricks
- Azure Storage Account
- VNet (Virtual Network)
- Key Vault
- Power BI

# Accessing Data Lake from Databricks

![cluster_access](/assets/cluster_access.gif)

## Access Azure Data Lake through an All-Purpose Cluster

### VNet Injection

1. Deploy the Azure Databricks resource on our virtual network (VNet). This setup ensures that clusters (excluding serverless ones) use IPs from our VNet IP address range.
2. Next, configure our network subnets (both private and public) in the networking settings of the Azure Data Lake (Storage Account).

### Service Principal

1. Instead of directly accessing the storage account, we use a service principal assigned with appropriate roles in Access Control (IAM).
2. All credentials are stored securely in Key Vault.

![cluster_access](/assets/key_vault.png)

3. Afterward, we use these values in the Spark configuration of the Databricks all-purpose cluster.

```
# Sets the authentication type to OAuth 
fs.azure.account.auth.type OAuth
# Specifies the type of OAuth token provider to use.
fs.azure.account.oauth.provider.type org.apache.hadoop.fs.azurebfs.oauth2.ClientCredsTokenProvider
# Client ID of the Azure AD application (Service Principal)
fs.azure.account.oauth2.client.id {{secrets/kv-stock-market/spn-stockmarket-storage-access-clientid}} 
# Client secret for the Service Principal
fs.azure.account.oauth2.client.secret {{secrets/kv-stock-market/spn-stockmarket-storage-access-clientsecret}}
# Specifies the OAuth 2.0 token endpoint 
# Format: https://login.microsoftonline.com/{Directory (tenant) ID}/oauth2/token
fs.azure.account.oauth2.client.endpoint {{secrets/kv-stock-market/az--oauth-endpoint}}
```

## Accessing Azure Data Lake through an All-Purpose Cluster

As shown in the diagram, although we deploy Azure Databricks on a Virtual Network, serverless clusters do not acquire IP addresses from this range. Serverless clusters are managed by Databricks servers rather than Azure servers. To enable data access from the storage account, we need to create a private endpoint using NCC (Network Connectivity Configurations).

When a private endpoint is added to an NCC, Azure Databricks creates a private endpoint request to your Azure resource. Once accepted, the private endpoint enables secure access from the serverless compute plane. This endpoint is dedicated to your Azure Databricks account and accessible only from authorized workspaces. [Documentation](https://learn.microsoft.com/en-us/azure/databricks/security/network/serverless-network-security/serverless-private-link)



# Power Bi Report
[Link to Power Bi Report](https://app.powerbi.com/view?r=eyJrIjoiNzFiOGZlZGQtZjdjYi00NTQ0LWI0OGYtNzYxMzY1YzA4NzlhIiwidCI6ImM1OGE5N2E3LTkzZTEtNDI4NC05ZDY5LWM2NzUyYmFmNzdhZiJ9)
![architecture](/assets/stock_report_gif.gif)