# Project Rules: FormOutreachBot

## Git & Deployment Protocol
- **Synchronous Git Push**: Always set `WaitMsBeforeAsync: 10000` when running `git push origin main` using `run_command`.
- **No Async Backgrounding for Git**: Never allow `git push` to run asynchronously in background tasks to prevent hang states across chat sessions.
- **Verify Deployment**: Confirm `git status` shows `Your branch is up to date with 'origin/main'` after pushing.
