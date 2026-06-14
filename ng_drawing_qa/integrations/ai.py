"""
AI integration hook.

This module intentionally does not call any external API by default.
Use ai_comment_drafts.csv as the safe offline output.

Future implementation:
- Read issue_log.csv
- Send only approved issue context to an internal/approved model
- Return suggested rewrites
- Never auto-approve engineering comments
"""
