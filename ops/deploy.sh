#!/usr/bin/env bash
set -Eeuo pipefail

AWS_REGION="${AWS_REGION:-us-east-1}"
STACK_NAME="${STACK_NAME:-AwsStockMarketPoc}"
SCHEDULE_STATE="${SCHEDULE_STATE:-DISABLED}"
REPOSITORY_NAME="${REPOSITORY_NAME:-aws-stock-market-poc}"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$PROJECT_DIR/.venv/bin/python}"
IMAGE_TAG="${IMAGE_TAG:-$(date -u +%Y%m%dT%H%M%SZ)}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="$(command -v python3)"
fi

ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
REPOSITORY_URI="${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${REPOSITORY_NAME}"

if ! aws ecr describe-repositories \
  --region "$AWS_REGION" \
  --repository-names "$REPOSITORY_NAME" >/dev/null 2>&1; then
  aws ecr create-repository \
    --region "$AWS_REGION" \
    --repository-name "$REPOSITORY_NAME" \
    --image-scanning-configuration scanOnPush=true >/dev/null
fi

aws ecr get-login-password --region "$AWS_REGION" |
  docker login --username AWS --password-stdin "${REPOSITORY_URI%/*}"

docker build --platform linux/arm64 \
  --provenance=false \
  -t "${REPOSITORY_URI}:${IMAGE_TAG}" "$PROJECT_DIR"
docker push "${REPOSITORY_URI}:${IMAGE_TAG}"

aws cloudformation deploy \
  --region "$AWS_REGION" \
  --stack-name "$STACK_NAME" \
  --template-file "$PROJECT_DIR/infrastructure/cloudformation/stack.yaml" \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides \
    ImageUri="${REPOSITORY_URI}:${IMAGE_TAG}" \
    ScheduleState="$SCHEDULE_STATE" \
  --no-fail-on-empty-changeset

"$PYTHON_BIN" "$PROJECT_DIR/ops/configure_secret.py" \
  --stack "$STACK_NAME" \
  --region "$AWS_REGION"

echo "Deployed Lambda image ${REPOSITORY_URI}:${IMAGE_TAG}"
echo "Daily schedule state: $SCHEDULE_STATE"
