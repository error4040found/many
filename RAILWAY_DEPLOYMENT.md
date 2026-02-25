# 🚀 Railway Deployment Guide — ManyChat Dashboard

## ✅ Why Railway?

| Feature | Railway | Vercel |
|---------|---------|--------|
| **Persistent Disk** | ✅ Yes (with Volume) | ❌ No |
| **SQLite Support** | ✅ Works perfectly | ❌ Data lost on cold start |
| **Long-running Server** | ✅ Always-on | ❌ Serverless (10s timeout) |
| **File Uploads** | ✅ Full support | ⚠️ /tmp only |
| **Free Tier** | ✅ $5 credit/month | ✅ Free (but limited) |
| **Custom Domain** | ✅ Free | ✅ Free |

---

## 📋 Step-by-Step Deployment

### Method 1: Deploy from GitHub (Recommended)

#### Step 1: Push fastapiapp to GitHub

Create a new GitHub repository and push ONLY the `fastapiapp/` folder:

```powershell
# Navigate to the fastapiapp folder
cd c:\Users\Administrator\Desktop\Manychatwithdashboard\fastapiapp

# Initialize git
git init

# Create .gitignore
echo "__pycache__/`n*.pyc`n*.db`n.env`nmanychat_dashboard.db" > .gitignore

# Add all files
git add .
git commit -m "ManyChat Dashboard - FastAPI app"

# Create repo on GitHub (or use GitHub Desktop)
# Then push:
git remote add origin https://github.com/YOUR_USERNAME/manychat-dashboard.git
git branch -M main
git push -u origin main
```

#### Step 2: Create Railway Account

1. Go to **https://railway.app**
2. Click **"Login"** → Sign in with **GitHub**
3. You get **$5 free credit/month** (no credit card required)

#### Step 3: Create New Project

1. Click **"New Project"** on the Railway dashboard
2. Select **"Deploy from GitHub Repo"**
3. Select your **manychat-dashboard** repository
4. Railway will auto-detect the Dockerfile and start building

#### Step 4: Set Environment Variables

In the Railway dashboard → Your Service → **Variables** tab → Click **"New Variable"**:

| Variable | Value | Required? |
|----------|-------|-----------|
| `DB_TYPE` | `sqlite` | ✅ Yes |
| `SQLITE_DB_PATH` | `/data/manychat_dashboard.db` | ✅ Yes (for persistent volume) |
| `SECRET_KEY` | `your-strong-random-secret-key-here` | ✅ Yes |
| `GOOGLE_APPS_SCRIPT_URL` | `https://script.google.com/macros/s/AKfycb.../exec` | Optional |
| `GOOGLE_SPREADSHEET_NAME` | `manychart` | Optional |
| `GOOGLE_SHEET_NAME` | `page_ids` | Optional |
| `EMAIL_SMTP_SERVER` | `smtp.gmail.com` | Optional |
| `EMAIL_SMTP_PORT` | `587` | Optional |
| `EMAIL_SENDER` | `alexrunway2004@gmail.com` | Optional |
| `EMAIL_PASSWORD` | `ulmq atmh mlbi kurk` | Optional |
| `EMAIL_RECIPIENTS` | `pveerababu199966@gmail.com,subhajit@spunkads.com` | Optional |

**If using MySQL instead of SQLite:**

| Variable | Value |
|----------|-------|
| `DB_TYPE` | `mysql` |
| `MYSQL_HOST` | `45.113.224.7` |
| `MYSQL_PORT` | `3306` |
| `MYSQL_USER` | `fundsill_babu` |
| `MYSQL_PASSWORD` | `Babu@7474` |
| `MYSQL_DATABASE` | `fundsill_gmail_automation` |

#### Step 5: Add a Persistent Volume (for SQLite)

If using SQLite, you MUST attach a volume so your database survives redeploys:

1. In Railway dashboard → Your Service → **Settings** tab
2. Scroll down to **"Volume"** → Click **"Attach Volume"**
3. Set:
   - **Mount Path**: `/data`
   - **Size**: `1 GB` (or more if needed)
4. Click **"Attach"**

This maps `/data` on the container to a persistent disk. Since we set `SQLITE_DB_PATH=/data/manychat_dashboard.db`, the database file will persist across deployments.

#### Step 6: Generate Domain

1. In Railway dashboard → Your Service → **Settings** tab
2. Scroll to **"Networking"** → Click **"Generate Domain"**
3. You'll get a URL like: `https://manychat-dashboard-production.up.railway.app`

#### Step 7: Access Your Dashboard

Open the generated URL in your browser:
- Login: `admin` / `admin@123`
- Or: `babu` / `babu@123`
- Or: `subhajit` / `subhajit@123`

---

### Method 2: Deploy from CLI (Quick)

```powershell
# 1. Install Railway CLI
npm install -g @railway/cli

# 2. Login
railway login

# 3. Navigate to fastapiapp
cd c:\Users\Administrator\Desktop\Manychatwithdashboard\fastapiapp

# 4. Initialize project
railway init

# 5. Link to a new project
railway link

# 6. Set environment variables
railway variables set DB_TYPE=sqlite
railway variables set SQLITE_DB_PATH=/data/manychat_dashboard.db
railway variables set SECRET_KEY=your-strong-random-secret-key-here

# 7. Deploy
railway up

# 8. Get your URL
railway domain
```

---

## 🔧 After Deployment: Seed the Database

Once deployed, your database will be empty. You need to seed it with your page_ids data.

### Option A: Upload via CSV (Easiest)

1. Login to your dashboard at the Railway URL
2. Click **"📤 Upload CSV"**
3. Upload a CSV file with columns: `page_id, name, user, tl, account_name`

### Option B: Seed via API

```python
import requests, json

URL = "https://your-app.up.railway.app"

# Login
s = requests.Session()
s.post(f"{URL}/login", data={"username": "admin", "password": "admin@123"}, allow_redirects=False)

# Import from page_ids.json
with open("page_ids.json") as f:
    data = json.load(f)

r = s.post(f"{URL}/api/page-ids/bulk-import", json=data)
print(r.json())
```

---

## 🔄 Updating After Code Changes

### From GitHub (auto-deploy)
Railway auto-deploys when you push to GitHub:
```powershell
cd c:\Users\Administrator\Desktop\Manychatwithdashboard\fastapiapp
git add .
git commit -m "Update dashboard"
git push
```
Railway will auto-detect the push and redeploy.

### From CLI
```powershell
cd c:\Users\Administrator\Desktop\Manychatwithdashboard\fastapiapp
railway up
```

---

## 📁 Project Structure for Railway

```
fastapiapp/
├── templates/
│   ├── base.html
│   ├── login.html
│   ├── dashboard.html
│   └── add_edit.html
├── static/
├── app.py              ← FastAPI application
├── database.py          ← DB config (SQLite / MySQL)
├── models.py            ← SQLAlchemy models
├── schemas.py           ← Pydantic schemas
├── auth.py              ← Authentication
├── seed_db.py           ← Database seeder
├── requirements.txt     ← Python dependencies
├── Dockerfile           ← Docker build config
├── Procfile             ← Start command
├── railway.toml         ← Railway-specific config
├── .dockerignore        ← Files excluded from Docker build
└── .gitignore           ← Files excluded from Git
```

---

## 🔍 Troubleshooting

### Build fails
- Check **Railway Logs** → Build tab for errors
- Ensure `requirements.txt` is in the root of the deployed directory

### App crashes on start
- Check **Railway Logs** → Deploy tab
- Most common: missing environment variable → add it in Variables tab

### Database not persisting
- Make sure you attached a **Volume** at mount path `/data`
- Make sure `SQLITE_DB_PATH=/data/manychat_dashboard.db` is set

### Can't connect to MySQL
- Ensure `45.113.224.7` allows Railway's IP range
- Railway IPs are dynamic — you may need to whitelist `0.0.0.0/0` or use Railway's MySQL addon

### Health check failing
- The health endpoint is `/api/health`
- Check if the app starts correctly in logs

---

## 💰 Railway Pricing

| Plan | Cost | What You Get |
|------|------|-------------|
| **Trial** | Free ($5 credit) | 500 hours, 1GB RAM, shared CPU |
| **Hobby** | $5/month | 8GB RAM, 8 vCPU, $5 usage included |
| **Pro** | $20/month | Team features, more resources |

Your dashboard is lightweight — the **Trial/Hobby** plan is more than enough.
