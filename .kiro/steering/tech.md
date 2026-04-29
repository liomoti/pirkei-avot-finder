# Technology Stack

## Backend (Serverless)

- **Runtime**: Python 3.12 on AWS Lambda
- **API**: API Gateway HTTP API with Cognito JWT authorizer
- **Database**: PostgreSQL on Supabase (accessed via pgbouncer pooler on port 6543)
- **ORM**: SQLAlchemy 2.x with plain declarative base (no Flask-SQLAlchemy)
- **Authentication**: Amazon Cognito User Pool (email/password, admin-only registration)
- **Semantic Search**: Bedrock Knowledge Base + Amazon Nova Pro via Converse API
- **Infrastructure as Code**: AWS SAM (template.yaml)

## Frontend

- **JavaScript**: Alpine.js 3.x for reactive components
- **CSS**: Tailwind CSS 2.x via CDN with custom Hebrew theme
- **Animations**: Lottie.js for loading states
- **Hosting**: S3 static website + CloudFront CDN

## AWS Services

- **Lambda**: 5 functions (search, semantic-search, admin, settings, auth)
- **API Gateway**: HTTP API with CORS, rate limiting, Cognito authorizer
- **S3**: Static frontend hosting
- **CloudFront**: CDN with custom domain (pirkei-avot.online) and ACM certificate
- **Cognito**: Admin authentication (USER_PASSWORD_AUTH flow)
- **Bedrock**: Knowledge Base retrieval + Nova Pro LLM reranking
- **ACM**: SSL certificate (in us-east-1 for CloudFront)

## Common Commands

### Build & Deploy
```bash
# Full deploy (build + deploy + S3 sync + CloudFront invalidation)
./scripts/deploy.sh

# Build only (uses Docker for Python 3.12 environment)
sam build --use-container

# Deploy only
sam deploy

# Validate template
sam validate --lint
```

### Frontend Only
```bash
# Sync frontend to S3
aws s3 sync frontend/ "s3://pirkei-avot.online-frontend" --region us-east-2 --delete

# Invalidate CloudFront cache
aws cloudfront create-invalidation --distribution-id E5J34MEGJDS08 --paths "/*"
```

### Testing
```bash
# Run tests
pytest tests/

# Test API endpoint directly
curl https://dvbs9w4c73suc.cloudfront.net/api/settings
```

### Cognito User Management
```bash
# Create admin user
aws cognito-idp admin-create-user \
  --user-pool-id us-east-2_DSgmdQdkE \
  --username "email@example.com" \
  --user-attributes Name=email,Value=email@example.com Name=email_verified,Value=true \
  --temporary-password "TempPass123" \
  --region us-east-2

# Set permanent password
aws cognito-idp admin-set-user-password \
  --user-pool-id us-east-2_DSgmdQdkE \
  --username "email@example.com" \
  --password "NewPassword123" \
  --permanent \
  --region us-east-2
```

## Environment Variables (via SAM template parameters)

Configured in `samconfig.toml` (gitignored):
- `DatabaseUrl`: Supabase PostgreSQL pooler connection string (port 6543)
- `KnowledgeBaseId`: Bedrock Knowledge Base ID (default: HAFIDLHKGC)
- `DomainName`: Custom domain (default: pirkei-avot.online)
- `AcmCertificateArn`: ACM certificate ARN (us-east-1)
- `PirushAttributionUrl`: Pirush attribution URL (default: https://www.veten.co.il)

## Performance Optimizations

- Lambda connection pooling: pool_size=1, max_overflow=0 per container
- Supabase pgbouncer pooler (port 6543) for connection multiplexing
- pool_pre_ping=True and pool_recycle=300 for connection health
- Module-level initialization for DB engine and boto3 clients (warm invocation reuse)
- Lambda-to-Lambda invoke for semantic search (no HTTP overhead)
- CloudFront caching for static assets, no caching for API responses
- API Gateway rate limiting: 20 req/min burst on search endpoints

## Region

All services deployed in `us-east-2` (Ohio), except ACM certificate in `us-east-1` (required by CloudFront).
