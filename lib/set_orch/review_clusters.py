from __future__ import annotations

"""Shared keyword clusters for review findings pattern matching.

Used by engine._persist_run_learnings() and dispatcher._build_review_learnings().
"""

REVIEW_PATTERN_CLUSTERS: dict[str, list[str]] = {
    "no-auth": ["no auth", "no authentication", "zero authentication", "without auth",
                 "unprotected", "missing auth", "missing authentication"],
    "no-csrf": ["csrf", "cross-site request"],
    "xss": ["xss", "dangerouslysetinnerhtml", "v-html"],
    "no-rate-limit": ["rate limit", "rate-limit"],
    "secrets-exposed": ["masking", "exposed", "leaked", "codes displayed"],
    "idor": ["idor", "ownership check", "authorization check", "other users",
             "other user", "sessionid", "where clause missing"],
    "cascade-delete": ["cascade", "financial data", "order history", "data loss"],
    "race-condition": ["race condition", "atomic", "double-spend", "oversell",
                       "non-atomic", "not atomic"],
    "missing-validation": ["input validation", "accepts negative", "zod validation",
                           "no validation", "missing validation"],
    "open-redirect": ["open redirect", "redirect vulnerability"],
    "i18n-hardcoded": ["hardcoded string", "hardcoded text", "hardcoded ui",
                        "untranslated", "missing translation", "missing i18n",
                        "usetranslations", "no i18n", "literal string",
                        "translation key", "i18n keys"],
    "ui-image": ["raw <img>", "<img>", "img tag", "img element",
                  "next/image", "image optimization"],
}
