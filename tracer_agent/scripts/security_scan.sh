#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════
# Purple Agent — Security Scan
# SAST (bandit) + Dependency Audit (pip-audit) + Anti-Pattern Check
# ═══════════════════════════════════════════════════════════════════

set -uo pipefail

FAIL=0

echo "═══════════════════════════════════════════════════════════"
echo "Purple Agent — Security Scan"
echo "═══════════════════════════════════════════════════════════"
echo ""

# ─── 1. Static Application Security Testing ──────────────────

echo "Section 1: SAST (bandit)"

if command -v bandit &> /dev/null; then
    # -ll = only medium and high severity
    # -ii = only medium and high confidence
    BANDIT_OUTPUT=$(bandit -r src/ -ll -ii --format txt 2>&1)
    BANDIT_EXIT=$?
    if [ "$BANDIT_EXIT" -eq 0 ]; then
        echo "  ✅ bandit: no medium/high issues found"
    else
        echo "  ❌ bandit: issues found"
        echo "$BANDIT_OUTPUT" | head -30
        FAIL=1
    fi
else
    echo "  ⚠️  bandit not installed (pip install bandit)"
fi

echo ""

# ─── 2. Dependency Vulnerability Audit ───────────────────────

echo "Section 2: Dependency Audit (pip-audit)"

if command -v pip-audit &> /dev/null; then
    AUDIT_OUTPUT=$(pip-audit --strict --desc 2>&1)
    AUDIT_EXIT=$?
    if [ "$AUDIT_EXIT" -eq 0 ]; then
        echo "  ✅ pip-audit: no known vulnerabilities"
    else
        echo "  ❌ pip-audit: vulnerabilities found"
        echo "$AUDIT_OUTPUT" | head -20
        FAIL=1
    fi
else
    echo "  ⚠️  pip-audit not installed (pip install pip-audit)"
fi

echo ""

# ─── 3. Anti-Pattern Enforcement ─────────────────────────────
# [HIGH-08] v3.0: Anti-pattern checks are authoritative in
# preflight.sh Section 8. Running them here too creates duplicate
# maintenance. Instead, we invoke preflight's checks by reference
# and add security-SPECIFIC static analysis that preflight lacks.

echo "Section 3: Source Code Security Analysis"

# 3.1 No eval() / exec() calls (code injection risk)
EVAL_EXEC=$(grep -rn "eval(\|exec(" src/ --include="*.py" 2>/dev/null | grep -v "#" | wc -l)
if [ "$EVAL_EXEC" -eq 0 ]; then
    echo "  ✅ No eval()/exec() (code injection)"
else
    echo "  ❌ Found $EVAL_EXEC eval()/exec() calls in src/"
    grep -rn "eval(\|exec(" src/ --include="*.py" | grep -v "#"
    FAIL=1
fi

# 3.2 No subprocess with shell=True (command injection risk)
SHELL_TRUE=$(grep -rn "shell=True" src/ --include="*.py" 2>/dev/null | wc -l)
if [ "$SHELL_TRUE" -eq 0 ]; then
    echo "  ✅ No subprocess shell=True (command injection)"
else
    echo "  ❌ Found $SHELL_TRUE shell=True in src/"
    FAIL=1
fi

# 3.3 No pickle.load / yaml.load without SafeLoader (deserialization)
UNSAFE_LOAD=$(grep -rn "pickle\.load\|yaml\.load(" src/ --include="*.py" 2>/dev/null | grep -v "SafeLoader\|safe_load" | wc -l)
if [ "$UNSAFE_LOAD" -eq 0 ]; then
    echo "  ✅ No unsafe deserialization"
else
    echo "  ❌ Found $UNSAFE_LOAD unsafe deserialization calls"
    FAIL=1
fi

# 3.4 No tempfile usage without secure patterns (temp file race)
TEMP_INSECURE=$(grep -rn "open('/tmp/" src/ --include="*.py" 2>/dev/null | wc -l)
if [ "$TEMP_INSECURE" -eq 0 ]; then
    echo "  ✅ No hardcoded /tmp paths (use tempfile module)"
else
    echo "  ⚠️  Found $TEMP_INSECURE hardcoded /tmp paths (prefer tempfile.mkstemp)"
fi

# 3.5 Anti-pattern enforcement is in preflight.sh Section 8
echo "  ℹ️  Anti-pattern checks (AP #2, #3, #10, #11, Rule 4, 15, 20) → run preflight.sh"

echo ""

# ─── 4. Secrets Leak Check ───────────────────────────────────

echo "Section 4: Secrets Leak Check"

# Check for common secret patterns in source code
SECRET_PATTERNS='(api_key|secret|password|token).*=.*["\x27][A-Za-z0-9+/=]{20,}'
SECRETS=$(grep -rniE "$SECRET_PATTERNS" src/ --include="*.py" 2>/dev/null | grep -v "os\.getenv\|os\.environ\|# " | wc -l)
if [ "$SECRETS" -eq 0 ]; then
    echo "  ✅ No hardcoded secrets detected"
else
    echo "  ❌ Possible hardcoded secrets found: $SECRETS matches"
    FAIL=1
fi

echo ""

# ─── Summary ─────────────────────────────────────────────────

echo "═══════════════════════════════════════════════════════════"
if [ "$FAIL" -gt 0 ]; then
    echo "❌ SECURITY SCAN FAILED — Fix issues above"
    exit 1
else
    echo "✅ SECURITY SCAN PASSED"
fi
