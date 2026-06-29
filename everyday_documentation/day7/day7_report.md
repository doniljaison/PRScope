# Day 7 Report

## What we did:
- **OAuth Setup**: Built the GitHub OAuth login flow (Authorize URL → Callback → Access Token).
- **Encryption**: Integrated `cryptography` (Fernet) to securely encrypt users' GitHub access tokens in the database.
- **User Linking**: Updated the user creation logic to seamlessly link a GitHub profile to an existing password-based account, or create a brand new account if none exists.
- **API Endpoints**: Added `/auth/github` and `/auth/github/callback` endpoints.
- **Testing**: Moked GitHub's API during tests to ensure our OAuth callback logic correctly generates JWTs.

Users can now seamlessly connect their GitHub accounts to PRScope!
