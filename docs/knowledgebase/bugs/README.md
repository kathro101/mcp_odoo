# Bug Reports

This directory contains bug reproduction records and fix documentation.

Format: `docs/knowledgebase/bugs/<YYYY-MM-DD>-<short-description>.md`

Template:

```markdown
# Bug: <Short Description>

**Date:** YYYY-MM-DD
**Found by:** <agent>
**Fixed by:** <agent>
**Severity:** [CRITICAL|HIGH|MEDIUM|LOW]

## Reproduction

1. Step 1
2. Step 2
   ...

## Expected Behavior

What should happen.

## Actual Behavior

What actually happened (error message, stack trace, etc.)

## Root Cause

The underlying issue.

## Fix

What was changed.

## Regression Test

`test_<name>` in `tests/test_<file>.py`
```
