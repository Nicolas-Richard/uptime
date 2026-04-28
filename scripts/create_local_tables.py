#!/usr/bin/env python3
"""Create DynamoDB tables for local development.

Reads table definitions from dynamodb_tables.json and creates them
against the endpoint specified by DYNAMODB_ENDPOINT_URL. Idempotent:
skips tables that already exist.
"""

import json
import os
import sys
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

TABLES_FILE = Path(__file__).parent / "dynamodb_tables.json"


def get_dynamodb_client():
    endpoint_url = os.environ.get("DYNAMODB_ENDPOINT_URL", "http://localhost:8001")
    region = os.environ.get("AWS_REGION", "us-east-1")
    return boto3.client(
        "dynamodb",
        endpoint_url=endpoint_url,
        region_name=region,
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID", "local"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY", "local"),
    )


def table_exists(client, table_name: str) -> bool:
    try:
        client.describe_table(TableName=table_name)
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceNotFoundException":
            return False
        raise


def create_tables():
    client = get_dynamodb_client()
    endpoint = os.environ.get("DYNAMODB_ENDPOINT_URL", "http://localhost:8001")

    with open(TABLES_FILE) as f:
        table_defs = json.load(f)

    for table_def in table_defs:
        table_name = table_def["TableName"]
        if table_exists(client, table_name):
            print(f"Table '{table_name}' already exists, skipping.")
            continue

        client.create_table(**table_def)
        print(f"Created table '{table_name}'.")

    print(f"Done. Endpoint: {endpoint}")


if __name__ == "__main__":
    create_tables()
