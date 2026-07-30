#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import boto3
from dotenv import dotenv_values


def find_api_key(project_dir: Path) -> str:
    candidates = (project_dir / ".env",)
    for path in candidates:
        if not path.exists():
            continue
        values = dotenv_values(path)
        value = values.get("TWELVE_DATA_API_KEY") or values.get("TWELWE-DATA-API")
        if value:
            return value
    raise RuntimeError(
        "No Twelve Data key found. Add TWELVE_DATA_API_KEY=... to .env"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stack", default="AwsStockMarketPoc")
    parser.add_argument("--region", default="us-east-1")
    args = parser.parse_args()

    project_dir = Path(__file__).resolve().parents[1]
    api_key = find_api_key(project_dir)
    cloudformation = boto3.client("cloudformation", region_name=args.region)
    secrets = boto3.client("secretsmanager", region_name=args.region)
    stacks = cloudformation.describe_stacks(StackName=args.stack)["Stacks"]
    outputs = {item["OutputKey"]: item["OutputValue"] for item in stacks[0]["Outputs"]}
    secret_arn = outputs["AppSecretArn"]
    current = json.loads(
        secrets.get_secret_value(SecretId=secret_arn)["SecretString"]
    )
    current["twelve_data_api_key"] = api_key
    secrets.put_secret_value(SecretId=secret_arn, SecretString=json.dumps(current))
    print(f"Updated Twelve Data key in {secret_arn}; secret value was not displayed.")


if __name__ == "__main__":
    main()
