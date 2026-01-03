# Pre-Deployment Checklist

## ✅ Before You Deploy

Run through this checklist to ensure everything is ready:

### 1. Verify Files Created ✓
- [ ] `core/middleware/__init__.py` exists
- [ ] `core/middleware/database.py` exists
- [ ] `gunicorn_config.py` exists in bdpricegear-backend/
- [ ] `products/management/commands/test_db_connection.py` exists

### 2. Verify Files Updated ✓
- [ ] `core/settings.py` has DatabaseConnectionMiddleware in MIDDLEWARE
- [ ] `products/views.py` has close_old_connections imports
- [ ] `Procfile` uses gunicorn_config.py
- [ ] `start.sh` uses gunicorn_config.py

### 3. Test Locally (Optional)
```bash
cd bdpricegear-backend
python manage.py test_db_connection
```
Expected output: ✅ Connection successful!

### 4. Commit Changes
```bash
git add .
git commit -m "Fix: Resolve database connection timeout issues

- Add database connection cleanup middleware
- Optimize database configuration with better timeouts
- Improve gunicorn worker management
- Add connection health checks
- Implement proper connection cleanup in views
- Add database connection testing tool"
git push
```

### 5. Monitor Deployment
After pushing:
- [ ] Check build logs for errors
- [ ] Wait for deployment to complete
- [ ] Test health endpoint: `curl https://your-app.com/api/health/`
- [ ] Verify: `"database": "connected"`

### 6. Post-Deployment Verification
- [ ] API responds without timeouts
- [ ] No "connection timeout expired" in logs
- [ ] Product listings load correctly
- [ ] Health check shows "connected"

## 🎯 Success Criteria

Your deployment is successful when:
1. ✅ Health endpoint returns `"database": "connected"`
2. ✅ No timeout errors in logs for 1+ hour
3. ✅ API responses are fast and consistent
4. ✅ Background tasks complete without errors

## 🚨 Rollback Plan (If Needed)

If something goes wrong:
1. Revert the commit: `git revert HEAD`
2. Push: `git push`
3. Contact support with error logs

## 📞 Support

If you encounter issues:
1. Check `docs/DATABASE_CONNECTION_FIX.md` for troubleshooting
2. Run the test command: `python manage.py test_db_connection --stress-test`
3. Check if DATABASE_URL uses port 5432 (session pooler)

---

**Ready to deploy?** ✅ All checks passed
**Estimated downtime**: < 2 minutes (during deployment)
**Risk level**: Low (backwards compatible changes)
