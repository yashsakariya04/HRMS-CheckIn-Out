# HRMS Backend Deployment Guide

This guide walks you through deploying the HRMS backend with PostgreSQL on Supabase and the FastAPI application on Render.

---

## Prerequisites

- GitHub account (to connect Render to your repository)
- Supabase account (free tier available at https://supabase.com)
- Render account (free tier available at https://render.com)
- Git installed locally
- Python 3.11+ installed locally

---

## Part 1: Database Setup on Supabase

### Step 1: Create a Supabase Project

1. Go to https://supabase.com and sign in
2. Click **New Project**
3. Fill in the details:
   - **Name**: `hrms-backend` (or your preferred name)
   - **Database Password**: Create a strong password and save it securely
   - **Region**: Choose the closest region to your users
   - **Pricing Plan**: Select Free tier
4. Click **Create new project** and wait 2-3 minutes for provisioning

### Step 2: Get Database Connection Strings

1. In your Supabase project dashboard, go to **Settings** → **Database**
2. Scroll down to **Connection string** section
3. Copy the **Connection pooling** URI (this uses port 5432 with pooler)
4. You'll need TWO versions:
   - **Async version** (for FastAPI): Replace `postgresql://` with `postgresql+asyncpg://`
   - **Sync version** (for Alembic migrations): Replace `postgresql://` with `postgresql+psycopg2://`
5. Replace `[YOUR-PASSWORD]` in both URLs with your actual database password

Example format:
```
# Async (for FastAPI)
postgresql+asyncpg://postgres.xxxxx:[YOUR-PASSWORD]@aws-0-region.pooler.supabase.com:5432/postgres

# Sync (for Alembic)
postgresql+psycopg2://postgres.xxxxx:[YOUR-PASSWORD]@aws-0-region.pooler.supabase.com:5432/postgres
```

### Step 3: Test Database Connection Locally

1. Update your local `.env` file with Supabase credentials:
```bash
DATABASE_URL=postgresql+asyncpg://postgres.xxxxx:[YOUR-PASSWORD]@aws-0-region.pooler.supabase.com:5432/postgres
SYNC_DATABASE_URL=postgresql+psycopg2://postgres.xxxxx:[YOUR-PASSWORD]@aws-0-region.pooler.supabase.com:5432/postgres
```

2. Test the connection:
```bash
python -c "from sqlalchemy import create_engine; engine = create_engine('postgresql+psycopg2://postgres.xxxxx:[YOUR-PASSWORD]@aws-0-region.pooler.supabase.com:5432/postgres'); conn = engine.connect(); print('✓ Connection successful'); conn.close()"
```

---

## Part 2: Run Database Migrations Locally

Before deploying to Render, set up the database schema from your local machine.

### Step 1: Install Dependencies

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# Install dependencies
pip install -r app/requirements.txt
```

### Step 2: Run Alembic Migrations

```bash
# Apply all migrations to create tables
alembic upgrade head
```

You should see output like:
```
INFO  [alembic.runtime.migration] Running upgrade -> c45ec8f8ef8e, initial partner schema
```

### Step 3: Verify Tables in Supabase

1. Go to Supabase dashboard → **Table Editor**
2. You should see 12 tables created:
   - organizations
   - department
   - employees
   - refresh_tokens
   - projects
   - attendance_sessions
   - task_entries
   - leave_policies
   - employee_leave_balances
   - leave_wfh_requests
   - holidays
   - audit_logs

### Step 4: Run Seed Script

```bash
python seed.py
```

This will populate:
- 1 organization (Infopulse)
- 4 departments (Engineering, Design, Product, HR)
- 4 leave policies (casual, sick, earned, comp_off)
- 4 demo employees (1 admin, 3 employees)
- Leave balances for current month
- 4 projects
- 7 national holidays for current year

Expected output:
```
Seeding database...

  [+] Organization : Infopulse
  [+] Department   : Engineering
  [+] Department   : Design
  [+] Department   : Product
  [+] Department   : HR
  [+] Leave policy : casual
  [+] Leave policy : sick
  [+] Leave policy : earned
  [+] Leave policy : comp_off
  [+] Employee     : Yash Sakariya <yash.infopulsetech@gmail.com> (admin)
  [+] Employee     : Nimisha <nimisha.infopulsetech@gmail.com> (employee)
  ...
```

---

## Part 3: Backend Deployment on Render

### Step 1: Push Code to GitHub

```bash
# Initialize git if not already done
git init

# Add all files
git add .

# Commit
git commit -m "Initial commit for deployment"

# Create a new repository on GitHub and push
git remote add origin https://github.com/YOUR-USERNAME/HRMS-backend.git
git branch -M main
git push -u origin main
```

### Step 2: Create Web Service on Render

1. Go to https://render.com and sign in
2. Click **New +** → **Web Service**
3. Connect your GitHub repository:
   - Click **Connect account** if first time
   - Select your `HRMS-backend` repository
   - Click **Connect**

### Step 3: Configure Web Service

Fill in the following settings:

**Basic Settings:**
- **Name**: `hrms-backend` (or your preferred name)
- **Region**: Choose same or closest to your Supabase region
- **Branch**: `main`
- **Root Directory**: Leave blank
- **Runtime**: `Python 3`
- **Build Command**: 
  ```
  pip install -r app/requirements.txt
  ```
- **Start Command**: 
  ```
  uvicorn app.main:app --host 0.0.0.0 --port $PORT
  ```

**Instance Type:**
- Select **Free** tier

### Step 4: Add Environment Variables

Click **Advanced** → **Add Environment Variable** and add the following:

| Key | Value |
|-----|-------|
| `DATABASE_URL` | Your Supabase async connection string (postgresql+asyncpg://...) |
| `JWT_SECRET_KEY` | Generate with: `openssl rand -hex 32` |
| `JWT_ALGORITHM` | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `365` |
| `SECRET_KEY` | Same as JWT_SECRET_KEY or generate another with `openssl rand -hex 32` |
| `GOOGLE_CLIENT_ID` | Your Google OAuth Client ID |
| `GOOGLE_CLIENT_SECRET` | Your Google OAuth Client Secret |
| `GOOGLE_REDIRECT_URI` | `https://YOUR-RENDER-APP.onrender.com/auth/callback` |
| `APP_ENV` | `production` |
| `CORS_ORIGINS` | Your frontend URL (e.g., `https://your-frontend.vercel.app`) |

**Important Notes:**
- Replace `YOUR-RENDER-APP` with your actual Render app name (you'll get this after creation)
- For `GOOGLE_REDIRECT_URI`, you may need to update this after deployment and add it to Google Cloud Console
- Keep `JWT_SECRET_KEY` and `SECRET_KEY` secure and never commit them to git

### Step 5: Deploy

1. Click **Create Web Service**
2. Render will start building and deploying your application
3. Wait 3-5 minutes for the first deployment
4. Once deployed, you'll see a green **Live** status

### Step 6: Get Your Render URL

1. Your app will be available at: `https://YOUR-APP-NAME.onrender.com`
2. Test the API:
   - Visit: `https://YOUR-APP-NAME.onrender.com/docs`
   - You should see the FastAPI Swagger documentation

---

## Part 4: Configure Google OAuth

### Step 1: Update Google Cloud Console

1. Go to https://console.cloud.google.com
2. Select your project
3. Navigate to **APIs & Services** → **Credentials**
4. Click on your OAuth 2.0 Client ID
5. Under **Authorized redirect URIs**, add:
   ```
   https://YOUR-APP-NAME.onrender.com/auth/callback
   ```
6. Click **Save**

### Step 2: Update Render Environment Variable

1. Go back to Render dashboard → Your service → **Environment**
2. Update `GOOGLE_REDIRECT_URI` to:
   ```
   https://YOUR-APP-NAME.onrender.com/auth/callback
   ```
3. Click **Save Changes**
4. Render will automatically redeploy

---

## Part 5: Update Frontend Configuration

Update your React frontend to point to the new backend URL:

```typescript
// In your frontend config or .env file
VITE_API_BASE_URL=https://YOUR-APP-NAME.onrender.com
```

Update CORS origins in Render:
1. Go to Render → Your service → **Environment**
2. Update `CORS_ORIGINS` to include your frontend URL:
   ```
   https://your-frontend.vercel.app,http://localhost:5173
   ```

---

## Part 6: Verify Deployment

### Test API Endpoints

1. **Health Check** (if you have one):
   ```bash
   curl https://YOUR-APP-NAME.onrender.com/
   ```

2. **API Documentation**:
   - Visit: `https://YOUR-APP-NAME.onrender.com/docs`

3. **Test Login**:
   - Use the Swagger UI to test the `/api/v1/auth/google/login` endpoint
   - Or test from your frontend application

### Check Database Connection

1. Go to Supabase → **Table Editor**
2. Check the `employees` table to verify seed data exists
3. Try logging in with one of the seeded accounts via Google OAuth

### Monitor Logs

1. In Render dashboard, go to **Logs** tab
2. Check for any errors or warnings
3. Verify the application started successfully:
   ```
   INFO:     Started server process
   INFO:     Waiting for application startup.
   INFO:     Application startup complete.
   INFO:     Uvicorn running on http://0.0.0.0:10000
   ```

---

## Part 7: Post-Deployment Tasks

### Set Up Automatic Deployments

Render automatically deploys when you push to your main branch. To deploy:

```bash
git add .
git commit -m "Your commit message"
git push origin main
```

Render will detect the push and redeploy automatically.

### Database Backups

Supabase automatically backs up your database daily on the free tier. To manually backup:

1. Go to Supabase → **Database** → **Backups**
2. Click **Create backup** for manual snapshots

### Monitor Application

1. **Render Metrics**: Check CPU, memory, and response times in Render dashboard
2. **Supabase Metrics**: Monitor database connections and query performance
3. **Logs**: Regularly check Render logs for errors

### Scale Up (When Needed)

**Render:**
- Upgrade to paid tier for:
  - No cold starts (free tier sleeps after 15 min inactivity)
  - More CPU and memory
  - Custom domains

**Supabase:**
- Upgrade to Pro tier for:
  - More database storage
  - Higher connection limits
  - Daily backups with point-in-time recovery

---

## Troubleshooting

### Issue: "Connection refused" or "Database connection failed"

**Solution:**
- Verify `DATABASE_URL` in Render environment variables
- Check Supabase project is active (not paused)
- Ensure password is URL-encoded (replace special characters)
- Test connection string locally first

### Issue: "Module not found" errors

**Solution:**
- Verify `app/requirements.txt` includes all dependencies
- Check build command in Render: `pip install -r app/requirements.txt`
- Review build logs in Render for specific missing packages

### Issue: "CORS policy" errors from frontend

**Solution:**
- Add your frontend URL to `CORS_ORIGINS` in Render
- Format: `https://your-frontend.com,http://localhost:5173`
- Redeploy after updating

### Issue: Google OAuth fails

**Solution:**
- Verify `GOOGLE_REDIRECT_URI` matches exactly in:
  - Render environment variables
  - Google Cloud Console authorized redirect URIs
- Check `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` are correct
- Ensure no trailing slashes in redirect URI

### Issue: Render app sleeps (free tier)

**Solution:**
- Free tier apps sleep after 15 minutes of inactivity
- First request after sleep takes 30-60 seconds to wake up
- Upgrade to paid tier to prevent sleeping
- Or use a service like UptimeRobot to ping your app every 10 minutes

### Issue: Migrations not applied

**Solution:**
- Run migrations locally first: `alembic upgrade head`
- Verify tables exist in Supabase Table Editor
- Don't run migrations from Render (run locally or via CI/CD)

---

## Security Checklist

- [ ] All environment variables are set in Render (not in code)
- [ ] `.env` file is in `.gitignore` and not committed
- [ ] JWT_SECRET_KEY is randomly generated and secure
- [ ] Database password is strong and not shared
- [ ] Google OAuth credentials are kept secret
- [ ] CORS_ORIGINS only includes trusted frontend URLs
- [ ] Supabase RLS (Row Level Security) policies reviewed if needed
- [ ] API rate limiting configured (if implemented)

---

## Maintenance

### Running New Migrations

When you add new models or modify existing ones:

1. Create migration locally:
   ```bash
   alembic revision --autogenerate -m "description of change"
   ```

2. Review the generated migration in `alembic/versions/`

3. Apply migration to Supabase:
   ```bash
   alembic upgrade head
   ```

4. Commit and push:
   ```bash
   git add .
   git commit -m "Add migration: description"
   git push origin main
   ```

### Adding New Seed Data

To add more employees, projects, or holidays:

1. Update `seed.py` with new data
2. Run locally: `python seed.py`
3. The script checks for existing records and only adds new ones

### Updating Dependencies

```bash
# Update requirements.txt
pip install --upgrade package-name
pip freeze > app/requirements.txt

# Commit and push
git add app/requirements.txt
git commit -m "Update dependencies"
git push origin main
```

---

## Cost Estimate

**Free Tier (Current Setup):**
- Supabase: Free (500 MB database, 2 GB bandwidth)
- Render: Free (750 hours/month, sleeps after inactivity)
- **Total: $0/month**

**Paid Tier (Recommended for Production):**
- Supabase Pro: $25/month (8 GB database, 50 GB bandwidth)
- Render Starter: $7/month (no sleeping, 512 MB RAM)
- **Total: $32/month**

---

## Support

- **Render Docs**: https://render.com/docs
- **Supabase Docs**: https://supabase.com/docs
- **FastAPI Docs**: https://fastapi.tiangolo.com

---

## Quick Reference

**Render Dashboard**: https://dashboard.render.com
**Supabase Dashboard**: https://app.supabase.com
**API Docs**: https://YOUR-APP-NAME.onrender.com/docs
**Backend URL**: https://YOUR-APP-NAME.onrender.com

---

**Deployment Complete!** 🚀

Your HRMS backend is now live and ready to handle requests from your React frontend.
