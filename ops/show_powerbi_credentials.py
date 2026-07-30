#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

import boto3


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stack", default="AwsStockMarketPoc")
    parser.add_argument("--region", default="us-east-1")
    args = parser.parse_args()
    cloudformation = boto3.client("cloudformation", region_name=args.region)
    outputs = {
        item["OutputKey"]: item["OutputValue"]
        for item in cloudformation.describe_stacks(StackName=args.stack)["Stacks"][0][
            "Outputs"
        ]
    }
    secrets = boto3.client("secretsmanager", region_name=args.region)
    value = json.loads(
        secrets.get_secret_value(SecretId=outputs["AppSecretArn"])["SecretString"]
    )
    print(f"API URL:  {outputs['ApiUrl']}")
    print(f"Username: {value['powerbi_username']}")
    print(f"Password: {value['powerbi_password']}")


if __name__ == "__main__":
    main()
