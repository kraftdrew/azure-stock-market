import os
from azure.identity import ClientSecretCredential, DefaultAzureCredential 
from azure.keyvault.secrets import SecretClient


# Using Credentials of identity currently logged in to the Azure CLI.
CLI_credentials = DefaultAzureCredential()


# Retrieve SPN credentials from environment variables
# client_id = os.getenv("AZURE_CLIENT_ID")
# client_secret = os.getenv("AZURE_CLIENT_SECRET")
# tenant_id = os.getenv("AZURE_TENANT_ID")




# Key Vault details
key_vault_name = "kv-stock-market"
key_vault_uri = f"https://{key_vault_name}.vault.azure.net"



# Initialize the SecretClient to interact with Azure Key Vault
secret_client = SecretClient(vault_url=key_vault_uri, credential=CLI_credentials)

# Retrieve a specific secret by name
secret_name = "az--oauth-endpoint"  # Replace with the actual name of the secret in Key Vault
apikey = secret_client.get_secret(secret_name).value

print(f"Secret Value: {apikey}")
