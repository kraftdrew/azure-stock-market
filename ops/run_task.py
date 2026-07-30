#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys

import boto3
from botocore.config import Config


def stack_outputs(client, stack_name: str) -> dict[str, str]:
    stack = client.describe_stacks(StackName=stack_name)["Stacks"][0]
    return {item["OutputKey"]: item["OutputValue"] for item in stack["Outputs"]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("daily", "backfill"), default="backfill")
    parser.add_argument("--stack", default="AwsStockMarketPoc")
    parser.add_argument("--region", default="us-east-1")
    args = parser.parse_args()

    cloudformation = boto3.client("cloudformation", region_name=args.region)
    outputs = stack_outputs(cloudformation, args.stack)
    client = boto3.client(
        "lambda",
        region_name=args.region,
        config=Config(
            read_timeout=910,
            connect_timeout=10,
            retries={"max_attempts": 0},
        ),
    )
    response = client.invoke(
        FunctionName=outputs["IngestionFunctionName"],
        InvocationType="RequestResponse",
        Payload=json.dumps({"mode": args.mode}).encode(),
    )
    payload = json.loads(response["Payload"].read() or b"{}")
    if response.get("FunctionError"):
        print(json.dumps(payload, indent=2), file=sys.stderr)
        raise RuntimeError(f"Lambda failed: {response['FunctionError']}")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
