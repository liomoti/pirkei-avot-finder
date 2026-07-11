#!/usr/bin/env bash
set -euo pipefail

STACK_NAME="pirkei-avot-serverless"
REGION="us-east-2"

echo "=== Syncing frontend files to S3 ==="
BUCKET_NAME=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='FrontendBucketName'].OutputValue" \
  --output text)

if [ -z "$BUCKET_NAME" ] || [ "$BUCKET_NAME" = "None" ]; then
  echo "Error: could not retrieve FrontendBucketName from stack outputs"
  exit 1
fi

aws s3 sync frontend/ "s3://${BUCKET_NAME}" --region "$REGION" --delete

echo "=== Invalidating CloudFront cache ==="
DISTRIBUTION_ID=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='CloudFrontDistributionId'].OutputValue" \
  --output text)

if [ -z "$DISTRIBUTION_ID" ] || [ "$DISTRIBUTION_ID" = "None" ]; then
  echo "Error: could not retrieve CloudFrontDistributionId from stack outputs"
  exit 1
fi

aws cloudfront create-invalidation \
  --distribution-id "$DISTRIBUTION_ID" \
  --paths "/*"

echo "=== Frontend deployment complete ==="
