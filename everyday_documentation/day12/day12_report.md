# Day 12 Report

## What we did:
- **Webhook Endpoint**: Created the `POST /api/v1/webhooks/github` route to receive events from GitHub.
- **HMAC Verification**: Implemented strict security checking using the `X-Hub-Signature-256` header to ensure only legitimate requests are processed.
- **Async Execution**: Configured the endpoint to trigger the Celery `analyze_pr_task` in the background and instantly return `202 Accepted` to avoid blocking GitHub.
- **Testing**: Added test cases for invalid signatures, missing headers, ignored events, and successful payload processing.
