# Simplified serverless migration

## Previous implementation

```text
EventBridge Scheduler
  -> ECS Fargate
  -> Python/Polars extraction
  -> S3 raw + bronze
  -> dbt/Athena staging + Iceberg gold
  -> versioned Power BI JSON
  -> API Gateway + Lambda
```

## Current implementation

```text
EventBridge Scheduler
  -> Docker Lambda
  -> S3 raw JSON + transformed Parquet

API Gateway
  -> Docker Lambda
  -> Athena SQL
  -> one Glue table
  -> transformed Parquet
```

## Removed components

- ECS cluster, task definition, networking, and Fargate runtime
- dbt project, seeds, snapshots, tests, and Athena adapter
- Bronze, staging, Gold, snapshot, and Power BI export datasets
- Iceberg table maintenance
- pre-generated JSON manifests and exports
- ECR lifecycle ownership from CloudFormation

ECR remains because the Lambda functions use a Docker image containing Polars.
The deployment script manages this repository and immutable image tags.

## Data contract

The only physical analytical dataset is `stock_market.prices`, located under:

```text
s3://DATA_BUCKET/transformed/prices/
```

The query Lambda generates `dim_symbol`, `dim_date`, and `fact_daily` results
with predefined Athena SQL. These are logical API projections, not additional
physical S3 datasets.

Existing objects under legacy prefixes are not read by the new architecture.
They can be archived or removed separately after the serverless cutover is
validated.

## Cutover

1. Deploy the stack with the schedule disabled.
2. Invoke the ingestion Lambda in `backfill` mode.
3. Confirm objects exist under `raw/` and `transformed/`.
4. Query `stock_market.prices` in Athena.
5. Test all REST endpoints using Basic authentication.
6. Refresh a copy of the Power BI model and compare totals.
7. Enable the daily schedule.
8. Remove legacy S3 prefixes only after validation and explicit approval.
