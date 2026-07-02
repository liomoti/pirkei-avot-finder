# Daily Development Guide — Pirkei Avot Finder

Quick reference for day-to-day development workflows.

---

## 1. Testing Frontend Locally (Before Deploy)

You can open the frontend files directly in a browser for layout and styling work. For anything that calls the API, you need a local server to avoid CORS issues.

### Option A: Python HTTP Server (Simplest)

```bash
cd frontend
python3 -m http.server 8080
```

Open `http://localhost:8080` in your browser.

**Limitation**: API calls go to the production CloudFront URL (hardcoded in the HTML). This means you're testing the UI against the live backend — which is fine for frontend-only changes (CSS, layout, Alpine.js logic). If you need to test against local Lambda functions, see Option B.

### Option B: SAM Local API (Full Local Stack)

Run the API Gateway + Lambda functions locally:

```bash
sam build --use-container
sam local start-api --port 3000
```

This starts a local API at `http://localhost:3000`. You'd need to temporarily point the frontend API base URL to `http://localhost:3000` instead of the CloudFront URL.

**Note**: This requires Docker running and a working database connection (the `DatabaseUrl` in `samconfig.toml` must be reachable from your machine). Semantic search won't work locally unless your machine has Bedrock access configured.

### Option C: Just Open the File

For pure HTML/CSS/layout changes, you can open the file directly:

```bash
open frontend/index.html
```

API calls will fail, but you can see styling, layout, animations, and Alpine.js component structure.

---

## 2. After a Frontend Change

If you only changed files in `frontend/` (HTML, CSS, images, JS), you do **not** need to rebuild the Lambda stack. Just sync to S3 and invalidate the CloudFront cache:

```bash
# Sync frontend to S3
aws s3 sync frontend/ "s3://pirkei-avot.online-frontend" --region us-east-2 --delete

# Invalidate CloudFront cache so changes appear immediately
aws cloudfront create-invalidation --distribution-id E5J34MEGJDS08 --paths "/*"
```

That's it. Changes go live in ~30 seconds after the invalidation propagates.

### One-Liner Version

```bash
aws s3 sync frontend/ "s3://pirkei-avot.online-frontend" --region us-east-2 --delete && aws cloudfront create-invalidation --distribution-id E5J34MEGJDS08 --paths "/*"
```

---

## 3. After a Lambda / Backend Change

If you changed files in `functions/` or `layers/shared/`, you need to rebuild and redeploy the SAM stack:

```bash
./scripts/deploy.sh
```

This runs the full pipeline:
1. `sam validate --lint` — checks the template for errors
2. `sam build --use-container` — builds Lambda packages in Docker (Python 3.12)
3. `sam deploy` — deploys the CloudFormation stack (updates only changed resources)
4. S3 sync — uploads frontend files
5. CloudFront invalidation — clears the CDN cache

**Requires**: Docker running (for the `--use-container` build step).

### Backend-Only Deploy (Skip Frontend)

If you're sure you only changed backend code and want to skip the S3 sync + CloudFront invalidation:

```bash
sam build --use-container
sam deploy
```

---

## 4. After a template.yaml Change

Any change to `template.yaml` (new Lambda, new API route, environment variable, IAM policy, etc.) requires a full deploy:

```bash
# Validate first to catch syntax errors
sam validate --lint

# Then full deploy
./scripts/deploy.sh
```

---

## 5. Quick Reference Table

| What Changed | Command |
|---|---|
| Frontend only (HTML/CSS/images) | `aws s3 sync frontend/ "s3://pirkei-avot.online-frontend" --region us-east-2 --delete && aws cloudfront create-invalidation --distribution-id E5J34MEGJDS08 --paths "/*"` |
| Lambda code (`functions/` or `layers/`) | `./scripts/deploy.sh` |
| SAM template (`template.yaml`) | `sam validate --lint && ./scripts/deploy.sh` |
| Everything | `./scripts/deploy.sh` |

---

## 6. Checking Logs After Deploy

If something breaks after deploying a Lambda change, check CloudWatch logs:

```bash
# Tail logs for a specific function (replace function name as needed)
sam logs --name SearchFunction --stack-name pirkei-avot-serverless --tail

# Other function names:
# SemanticSearchFunction
# AdminFunction
# SettingsFunction
# AuthFunction
```

Or check logs for the last 10 minutes:

```bash
sam logs --name SearchFunction --stack-name pirkei-avot-serverless --start-time '10min ago'
```

---

## 7. Running Tests

```bash
pytest tests/
```

Run a specific test file:

```bash
pytest tests/test_response.py -v
```

---

## 8. Common Gotchas

- **CloudFront cache**: After a frontend deploy, if you don't see changes, make sure the invalidation completed. You can check status in the AWS Console under CloudFront > Distributions > Invalidations.
- **Docker must be running** for `sam build --use-container`. If Docker is off, the build will fail.
- **Database connection**: Lambda connects to Supabase via the pgbouncer pooler (port 6543). If you see connection errors, check that the Supabase project is active and the password hasn't changed.
- **Cognito tokens expire**: If admin panel stops working, log out and log back in to get a fresh JWT.
- **sam deploy is incremental**: It only updates resources that changed. If only one Lambda's code changed, only that function gets redeployed — the rest stay untouched.

---

## 9. Typical Development Cycle

```
1. Make changes locally
2. Test in browser (python3 -m http.server 8080 for frontend)
3. Commit to git
4. Deploy:
   - Frontend only → s3 sync + CloudFront invalidation
   - Backend/infra → ./scripts/deploy.sh
5. Verify on https://pirkei-avot.online
6. Check CloudWatch logs if something is off
```
