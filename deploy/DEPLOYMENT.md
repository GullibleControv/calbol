# CalBol Deployment Guide - DigitalOcean

## Prerequisites
- DigitalOcean account
- Domain name (optional, can use IP initially)
- Your code pushed to GitHub

---

## Step 1: Create DigitalOcean Droplet

1. Login to https://cloud.digitalocean.com
2. Click **Create** → **Droplets**
3. Configure:
   - **Region**: Choose closest to your users
   - **Image**: Ubuntu 24.04 LTS
   - **Size**: Basic → Regular → $6/month (1GB RAM)
   - **Authentication**: SSH Key (recommended)
   - **Hostname**: calbol-server

4. Click **Create Droplet**
5. Note your IP address (e.g., `143.198.45.123`)

---

## Step 2: Connect to Your Server

### From Windows (PowerShell):
```powershell
ssh root@YOUR_IP_ADDRESS
```

### First time setup (security):
```bash
# Update system
apt update && apt upgrade -y

# Create non-root user (optional but recommended)
adduser calbol
usermod -aG sudo calbol

# Set up firewall
ufw allow OpenSSH
ufw allow 'Nginx Full'
ufw enable
```

---

## Step 3: Install Dependencies

```bash
# Install required packages
apt install -y python3 python3-pip python3-venv nginx redis-server git curl

# Verify installations
python3 --version
nginx -v
redis-cli ping  # Should return PONG
```

---

## Step 4: Set Up Application

### 4.1 Create directories
```bash
mkdir -p /var/www/calbol
mkdir -p /var/log/calbol
cd /var/www/calbol
```

### 4.2 Clone your repository
```bash
# Option A: From GitHub (recommended)
git clone https://github.com/YOUR_USERNAME/calbol.git .

# Option B: Upload via SCP (from your local machine)
# scp -r C:\projects\calbol\* root@YOUR_IP:/var/www/calbol/
```

### 4.3 Create virtual environment
```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install gunicorn
```

### 4.4 Configure environment
```bash
# Copy and edit environment file
cp .env.example .env
nano .env
```

Edit `.env` with production values:
```env
SECRET_KEY=generate-a-long-random-string-here
DEBUG=False
ALLOWED_HOSTS=YOUR_IP_ADDRESS,yourdomain.com

DATABASE_URL=postgresql://postgres:PASSWORD@db.PROJECT.supabase.co:5432/postgres
REDIS_URL=redis://localhost:6379/0
OPENAI_API_KEY=sk-your-key
```

Generate a secret key:
```bash
python3 -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

### 4.5 Run Django setup
```bash
source venv/bin/activate
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser
```

### 4.6 Set permissions
```bash
chown -R www-data:www-data /var/www/calbol
chown -R www-data:www-data /var/log/calbol
chmod -R 755 /var/www/calbol
```

---

## Step 5: Configure Nginx

### 5.1 Create site configuration
```bash
cp /var/www/calbol/deploy/nginx.conf /etc/nginx/sites-available/calbol

# Edit and replace YOUR_DOMAIN_OR_IP
nano /etc/nginx/sites-available/calbol
```

Change this line:
```nginx
server_name YOUR_DOMAIN_OR_IP;
```
To your IP or domain:
```nginx
server_name 143.198.45.123;  # or yourdomain.com
```

### 5.2 Enable site
```bash
ln -s /etc/nginx/sites-available/calbol /etc/nginx/sites-enabled/
rm /etc/nginx/sites-enabled/default

# Test configuration
nginx -t

# Restart Nginx
systemctl restart nginx
```

---

## Step 6: Set Up Systemd Services

### 6.1 Copy service files
```bash
cp /var/www/calbol/deploy/calbol.service /etc/systemd/system/
cp /var/www/calbol/deploy/celery.service /etc/systemd/system/
```

### 6.2 Enable and start services
```bash
systemctl daemon-reload
systemctl enable calbol celery
systemctl start calbol celery

# Check status
systemctl status calbol
systemctl status celery
```

---

## Step 7: Test Your Deployment

Open in browser:
```
http://YOUR_IP_ADDRESS/
http://YOUR_IP_ADDRESS/admin/
http://YOUR_IP_ADDRESS/api/v1/
```

---

## Step 8: Add SSL Certificate (HTTPS)

### 8.1 Point domain to server (if using domain)
In your domain registrar (Namecheap, Cloudflare, etc.):
- Add an **A Record**: `@` → `YOUR_IP_ADDRESS`
- Add an **A Record**: `www` → `YOUR_IP_ADDRESS`

Wait 5-30 minutes for DNS propagation.

### 8.2 Install Certbot
```bash
apt install certbot python3-certbot-nginx -y
```

### 8.3 Get SSL certificate
```bash
certbot --nginx -d yourdomain.com -d www.yourdomain.com
```

Follow the prompts:
- Enter email for renewal notices
- Agree to terms
- Choose to redirect HTTP to HTTPS (recommended)

### 8.4 Auto-renewal
Certbot sets up auto-renewal. Test it:
```bash
certbot renew --dry-run
```

---

## Useful Commands

### View logs
```bash
# Application logs
journalctl -u calbol -f

# Celery logs
journalctl -u celery -f

# Nginx logs
tail -f /var/log/nginx/error.log
tail -f /var/log/calbol/access.log
```

### Restart services
```bash
systemctl restart calbol
systemctl restart celery
systemctl restart nginx
```

### Update application
```bash
cd /var/www/calbol
git pull origin master
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
systemctl restart calbol celery
```

---

## Troubleshooting

### 502 Bad Gateway
```bash
# Check if Gunicorn is running
systemctl status calbol

# Check socket exists
ls -la /var/www/calbol/calbol.sock

# Check permissions
chown www-data:www-data /var/www/calbol/calbol.sock
```

### Static files not loading
```bash
python manage.py collectstatic --noinput
chown -R www-data:www-data /var/www/calbol/staticfiles/
```

### Database connection errors
- Check your Supabase connection string in `.env`
- Ensure your server IP is allowed in Supabase (Database → Settings → Network)

---

## Cost Summary

| Service | Cost |
|---------|------|
| DigitalOcean Droplet (1GB) | $6/month |
| Domain (optional) | ~$10/year |
| SSL (Let's Encrypt) | Free |
| Supabase (free tier) | Free |
| **Total** | **$6-7/month** |
