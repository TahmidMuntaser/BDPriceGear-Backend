#!/bin/bash
# Commit Guide for BDPriceGear Backend Security Fixes

echo "================================================"
echo "BDPriceGear - Safe Commit Guide"
echo "================================================"
echo ""

# Check if we're in git repo
if [ ! -d .git ]; then
    echo "❌ Error: Not in a git repository"
    exit 1
fi

echo "✅ Git repository detected"
echo ""

# Check for sensitive files
echo "🔍 Checking for sensitive files..."
if git ls-files | grep -q "\.env$"; then
    echo "❌ WARNING: .env file is tracked by git!"
    echo "   Run: git rm --cached bdpricegear-backend/.env"
    echo ""
fi

echo "📝 Files safe to commit:"
echo ""

# Show what will be committed
git status --short

echo ""
echo "================================================"
echo "COMMIT CHECKLIST:"
echo "================================================"
echo ""
echo "✅ Before committing, verify:"
echo ""
echo "  1. .env is NOT in git"
echo "     Run: git rm --cached bdpricegear-backend/.env"
echo ""
echo "  2. .env.example IS in git (template only)"
echo "     Run: git add .env.example"
echo ""
echo "  3. No passwords in code"
echo "     Run: git grep -i password | grep -v example"
echo ""
echo "  4. No secret keys in code" 
echo "     Run: git grep SECRET_KEY | grep -v example | grep -v settings.py"
echo ""
echo "================================================"
echo "RECOMMENDED COMMIT:"
echo "================================================"
echo ""
echo "git add \\"
echo "  bdpricegear-backend/core/settings.py \\"
echo "  bdpricegear-backend/products/views.py \\"
echo "  bdpricegear-backend/products/management/commands/verify_scraping_setup.py \\"
echo "  start.sh \\"
echo "  nixpacks.toml \\"
echo "  setup_cache.sh \\"
echo "  setup_cache.bat \\"
echo "  .env.example \\"
echo "  SECURITY_REVIEW.md"
echo ""
echo "git commit -m \"Fix: Add rate limiting and security improvements"
echo ""
echo "- Add rate limiting to scraping endpoints (3 req/hour)"
echo "- Add production security headers (HSTS, XSS protection)"
echo "- Add cache configuration for scraping state"
echo "- Add setup scripts and verification tool"
echo "- Create .env.example template"
echo "\""
echo ""
echo "================================================"
echo "⚠️  AFTER COMMITTING - ROTATE CREDENTIALS:"
echo "================================================"
echo ""
echo "Since .env file contained real credentials (even if not committed),"
echo "you should rotate them for security:"
echo ""
echo "1. Supabase: Reset database password"
echo "2. Upstash: Reset Redis password"
echo "3. Django: Generate new SECRET_KEY"
echo "4. Update production environment variables"
echo ""
echo "Generate new SECRET_KEY:"
echo "  python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'"
echo ""
echo "================================================"
