# Deployment Guide — Pirkei Avot Finder (Serverless)

This guide walks you through deploying the serverless Pirkei Avot Finder to AWS using the AWS SAM CLI.

The deployment follows a safe two-phase approach:
1. **Phase 1**: Deploy the stack and test everything on the CloudFront URL
2. **Phase 2**: Once verified, connect your custom domain (`pirkei-avot.online`)

This way your users on the current Render deployment are not affected until you're confident the new stack works.

---

## Prerequisites

1. **AWS CLI** — installed and configured with credentials (`aws configure`)
2. **AWS SAM CLI** — [install guide](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html)
3. **Python 3.12** — required for Lambda runtime (all Lambda functions use Python 3.12). Your local Python version doesn't matter if you use `sam build --use-container` (Docker handles it).
4. **Docker** — required by `sam build --use-container` to package Lambda layers with native dependencies (psycopg2) in a Python 3.12 environment

Verify your setup:

```bash
aws --version
sam --version
docker --version
```

## Project Structure

```
├── template.yaml          # SAM infrastructure template
├── samconfig.toml         # Deployment configuration (gitignored — contains secrets)
├── scripts/deploy.sh      # Automated deployment script
├── functions/
│   ├── search/            # Search Lambda handler
│   ├── semantic_search/   # Semantic Search Lambda (Bedrock KB + Nova Pro reranking)
│   ├── admin/             # Admin CRUD Lambda handler
│   ├── settings/          # Settings Lambda handler
│   └── auth/              # Cognito auth Lambda handler
├── layers/shared/
│   ├── python/            # Shared Lambda layer (models, db, utils)
│   └── requirements.txt   # Layer dependencies
└── frontend/              # Static site (S3 + CloudFront)
    ├── index.html
    ├── manage.html
    ├── login.html
    ├── error.html
    └── static/
```

---

## Phase 1: Deploy and Test

### Step 1: Configure Parameters

Edit `samconfig.toml` and fill in the `parameter_overrides`:

```toml
parameter_overrides = "DatabaseUrl=\"postgresql://postgres.gxruaixnpaxgoivdnrem:<PASSWORD>@aws-0-eu-central-1.pooler.supabase.com:6543/postgres\" DomainName=\"pirkei-avot.online\" AcmCertificateArn=\"\""
```

Replace `<PASSWORD>` with your Supabase database password.

> **Important**: Use port `6543` (Supabase connection pooler), not `5432` (direct). Lambda's concurrent invocations can exhaust direct connection limits. The pooler URL is the same host — just change the port.

Leave `AcmCertificateArn` empty for now — we'll add it in Phase 2.

#### Parameter Reference

| Parameter | Description | Example |
|---|---|---|
| `DatabaseUrl` | Supabase PostgreSQL pooler connection string (port 6543) | `postgresql://postgres.xxx:pass@aws-0-eu-central-1.pooler.supabase.com:6543/postgres` |
| `KnowledgeBaseId` | Bedrock Knowledge Base ID for semantic search (default: `HAFIDLHKGC`) | `HAFIDLHKGC` |
| `DomainName` | Your custom domain (default: `pirkei-avot.online`) | `pirkei-avot.online` |
| `AcmCertificateArn` | ACM certificate ARN — leave empty for Phase 1 | `arn:aws:acm:us-east-1:...` |
| `PirushAttributionUrl` | Attribution URL for pirush (default: `https://www.veten.co.il`) | — |

#### Region

The default region is `us-east-2` (Ohio), matching the Bedrock Knowledge Base and Nova Pro model:

```toml
region = "us-east-2"
```

#### Bedrock Prerequisites

Before deploying, make sure:

1. The Bedrock Knowledge Base (`HAFIDLHKGC`) exists in `us-east-2` with your Pirkei Avot documents indexed
2. The `us.amazon.nova-pro-v1:0` model is enabled in your account (Bedrock > Model access in the AWS console)

### Step 2: Deploy

Run the automated deployment script:

```bash
chmod +x scripts/deploy.sh
./scripts/deploy.sh
```

This runs `sam build --use-container`, `sam deploy`, syncs the frontend to S3, and invalidates the CloudFront cache.

Alternatively, for a first-time guided deploy:

```bash
sam deploy --guided
```

### Step 3: Create an Admin User

```bash
# Get the User Pool ID from stack outputs
POOL_ID=$(aws cloudformation describe-stacks \
  --stack-name pirkei-avot-serverless \
  --query "Stacks[0].Outputs[?OutputKey=='CognitoUserPoolId'].OutputValue" \
  --output text)

# Create the admin user
aws cognito-idp admin-create-user \
  --user-pool-id "$POOL_ID" \
  --username "admin@example.com" \
  --user-attributes Name=email,Value=admin@example.com Name=email_verified,Value=true \
  --temporary-password "TempPass123"

# Set a permanent password (skip the force-change-password flow)
aws cognito-idp admin-set-user-password \
  --user-pool-id "$POOL_ID" \
  --username "admin@example.com" \
  --password "YourSecurePassword123" \
  --permanent
```

### Step 4: Test on CloudFront URL

Get the CloudFront URL from the stack outputs:

```bash
aws cloudformation describe-stacks \
  --stack-name pirkei-avot-serverless \
  --query "Stacks[0].Outputs[?OutputKey=='CloudFrontUrl'].OutputValue" \
  --output text
```

This gives you something like `https://d1234abcdef.cloudfront.net`. Test everything:

| What to Test | URL |
|---|---|
| Main search page | `https://d1234abcdef.cloudfront.net` |
| Settings API | `https://d1234abcdef.cloudfront.net/api/settings` |
| Chapter search | `https://d1234abcdef.cloudfront.net/api/search/mishna?chapter=א&mishna=all` |
| Smart search | `https://d1234abcdef.cloudfront.net/api/search/smart?q=תורה&exact_match=false` |
| Admin login | `https://d1234abcdef.cloudfront.net/login.html` |
| Admin panel | `https://d1234abcdef.cloudfront.net/manage.html` (after login) |

**Checklist:**
- [ ] Main page loads with correct styling and Hebrew RTL layout
- [ ] Chapter/mishna search returns results
- [ ] Smart search (exact match) works
- [ ] Smart search (semantic/AI) works
- [ ] Tag-based search works
- [ ] Navigate by number (prev/next) works
- [ ] Pirush modal opens and loads PDF
- [ ] Admin login works with the Cognito user you created
- [ ] Admin panel: create/update mishna, add/edit/delete tags, add categories
- [ ] Pirush toggle works from admin panel
- [ ] Logout works

> **Note**: During Phase 1, CORS is configured for `https://pirkei-avot.online`. If you get CORS errors testing on the CloudFront URL, temporarily add the CloudFront domain to the CORS config in `template.yaml` under `AllowOrigins`, redeploy, and remove it before Phase 2.

---

## Phase 2: Connect Custom Domain

Once everything works on the CloudFront URL, connect `pirkei-avot.online`.

### Step 1: Create an ACM Certificate (must be in us-east-1)

CloudFront requires SSL certificates to be in `us-east-1`, regardless of your stack's region.

```bash
aws acm request-certificate \
  --domain-name pirkei-avot.online \
  --validation-method DNS \
  --region us-east-1
```

Note the returned `CertificateArn`.

### Step 2: Validate the Certificate

```bash
aws acm describe-certificate \
  --certificate-arn <your-certificate-arn> \
  --region us-east-1 \
  --query "Certificate.DomainValidationOptions[0].ResourceRecord"
```

Go to your domain registrar's DNS settings and add the CNAME record shown (Name → Value). ACM validates automatically — usually takes a few minutes.

Wait until the certificate status is `Issued`:

```bash
aws acm describe-certificate \
  --certificate-arn <your-certificate-arn> \
  --region us-east-1 \
  --query "Certificate.Status"
```

### Step 3: Update samconfig.toml and Redeploy

Add the certificate ARN:

```toml
parameter_overrides = "DatabaseUrl=\"...\" DomainName=\"pirkei-avot.online\" AcmCertificateArn=\"arn:aws:acm:us-east-1:123456789:certificate/abc-123\""
```

Redeploy:

```bash
./scripts/deploy.sh
```

### Step 4: Point Your Domain to CloudFront

At your domain registrar, update the DNS:

- **Type**: CNAME (or ALIAS/ANAME if your registrar supports it for root domains)
- **Name**: `@` or `pirkei-avot.online`
- **Value**: `d1234abcdef.cloudfront.net` (your CloudFront distribution domain)

DNS propagation usually takes a few minutes but can take up to 48 hours.

### Step 5: Verify

```bash
curl -I https://pirkei-avot.online
```

You should see a 200 response with CloudFront headers. Once confirmed, you can decommission the Render deployment.

---

## Architecture Note — Semantic Search

The search handler invokes the Semantic Search Lambda directly (Lambda-to-Lambda via `boto3.client('lambda').invoke()`) — no HTTP API Gateway in between. This is faster and simpler than the previous HTTP-based approach. The Semantic Search Lambda:

1. Queries the Bedrock Knowledge Base for the top 20 vector search candidates
2. Sends candidates to Amazon Nova Pro (via the Converse API) for LLM-based relevance filtering
3. Returns a dict of `{mishna_number: relevance_score}` back to the search handler

---

## Ongoing Operations

### Code Changes (Lambda)

```bash
./scripts/deploy.sh
```

### Frontend Changes Only

No need to redeploy the stack — just sync and invalidate:

```bash
BUCKET=$(aws cloudformation describe-stacks \
  --stack-name pirkei-avot-serverless \
  --query "Stacks[0].Outputs[?OutputKey=='FrontendBucketName'].OutputValue" \
  --output text)

DIST_ID=$(aws cloudformation describe-stacks \
  --stack-name pirkei-avot-serverless \
  --query "Stacks[0].Outputs[?OutputKey=='CloudFrontDistributionId'].OutputValue" \
  --output text)

aws s3 sync frontend/ "s3://${BUCKET}" --delete
aws cloudfront create-invalidation --distribution-id "$DIST_ID" --paths "/*"
```

### Stack Outputs Reference

| Output | What It Is |
|---|---|
| `CloudFrontUrl` | Your site's public URL |
| `HttpApiUrl` | API Gateway endpoint (CloudFront proxies `/api/*` here) |
| `CognitoUserPoolId` | Cognito User Pool ID |
| `CognitoUserPoolClientId` | Cognito Client ID |
| `FrontendBucketName` | S3 bucket holding the static frontend |
| `CloudFrontDistributionId` | CloudFront distribution ID (for cache invalidation) |

---

## Tearing Down

To delete all AWS resources created by this stack:

```bash
# Empty the S3 bucket first (required before stack deletion)
aws s3 rm "s3://$(aws cloudformation describe-stacks \
  --stack-name pirkei-avot-serverless \
  --query "Stacks[0].Outputs[?OutputKey=='FrontendBucketName'].OutputValue" \
  --output text)" --recursive

# Delete the stack
sam delete --stack-name pirkei-avot-serverless
```

---

## Troubleshooting

### `sam build` fails with psycopg2 errors
The deploy script uses `sam build --use-container` which builds inside Docker with Python 3.12. Make sure Docker is running.

### CORS errors in the browser
The API Gateway CORS config only allows `https://pirkei-avot.online`. During Phase 1 testing on the CloudFront URL, you may need to temporarily add the CloudFront domain to `AllowOrigins` in `template.yaml`.

### 401 on admin endpoints
Make sure you're passing the JWT token in the `Authorization: Bearer <token>` header. Check that the Cognito user exists and the password is set to permanent (not temporary).

### Lambda timeout / DB connection errors
Check that the `DatabaseUrl` uses the Supabase pooler endpoint (port `6543`, not `5432`). Verify the database is accessible from Lambda (Supabase allows connections from any IP by default).

### CloudFront serving stale content
```bash
aws cloudfront create-invalidation --distribution-id "$DIST_ID" --paths "/*"
```

### Semantic search returns no results or errors
- Verify the Bedrock Knowledge Base ID (`HAFIDLHKGC`) is correct and the KB exists in `us-east-2`
- Check that the `us.amazon.nova-pro-v1:0` model is enabled in Bedrock Model Access
- Check CloudWatch logs for the `pirkei-avot-semantic-search` Lambda
- The semantic search Lambda has a 60s timeout — if Bedrock is slow, you may see timeouts

### Custom domain not working (Phase 2)
- Make sure the ACM certificate status is `Issued` — check with `aws acm describe-certificate --certificate-arn <arn> --region us-east-1`
- The ACM certificate must be in `us-east-1` — CloudFront won't accept certs from other regions
- DNS propagation can take up to 48 hours, but usually completes within minutes
- If your registrar doesn't support CNAME on root domain (`@`), use an ALIAS/ANAME record or `www.pirkei-avot.online`
