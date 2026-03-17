#!/bin/bash
# CalBol Server Setup Script
# Run this on a fresh Ubuntu 24.04 server
# Usage: sudo bash setup_server.sh

set -e  # Exit on error

echo "=========================================="
echo "CalBol Server Setup"
echo "=========================================="

# Update system
echo "[1/8] Updating system packages..."
apt update && apt upgrade -y

# Install dependencies
echo "[2/8] Installing dependencies..."
apt install -y python3 python3-pip python3-venv nginx redis-server git curl

# Create app directory
echo "[3/8] Creating app directory..."
mkdir -p /var/www/calbol
mkdir -p /var/log/calbol
chown -R www-data:www-data /var/www/calbol
chown -R www-data:www-data /var/log/calbol

# Clone repository (replace with your repo URL)
echo "[4/8] Cloning repository..."
echo "NOTE: You need to manually clone your repo or upload files"
echo "      git clone https://github.com/YOUR_USERNAME/calbol.git /var/www/calbol"
echo ""

# Instructions for manual steps
echo "=========================================="
echo "MANUAL STEPS REQUIRED:"
echo "=========================================="
echo ""
echo "1. Upload your code to /var/www/calbol/"
echo "   Option A: git clone https://github.com/YOUR_USERNAME/calbol.git /var/www/calbol"
echo "   Option B: scp -r your-local-path/* root@your-server:/var/www/calbol/"
echo ""
echo "2. Create virtual environment and install dependencies:"
echo "   cd /var/www/calbol"
echo "   python3 -m venv venv"
echo "   source venv/bin/activate"
echo "   pip install -r requirements.txt"
echo "   pip install gunicorn"
echo ""
echo "3. Create .env file with production settings:"
echo "   cp .env.example .env"
echo "   nano .env  # Edit with your production values"
echo ""
echo "4. Run setup commands:"
echo "   python manage.py migrate"
echo "   python manage.py collectstatic --noinput"
echo "   python manage.py createsuperuser"
echo ""
echo "5. Set permissions:"
echo "   chown -R www-data:www-data /var/www/calbol"
echo ""
echo "6. Set up Nginx:"
echo "   cp /var/www/calbol/deploy/nginx.conf /etc/nginx/sites-available/calbol"
echo "   nano /etc/nginx/sites-available/calbol  # Replace YOUR_DOMAIN_OR_IP"
echo "   ln -s /etc/nginx/sites-available/calbol /etc/nginx/sites-enabled/"
echo "   rm /etc/nginx/sites-enabled/default  # Remove default site"
echo "   nginx -t  # Test configuration"
echo "   systemctl restart nginx"
echo ""
echo "7. Set up systemd services:"
echo "   cp /var/www/calbol/deploy/calbol.service /etc/systemd/system/"
echo "   cp /var/www/calbol/deploy/celery.service /etc/systemd/system/"
echo "   systemctl daemon-reload"
echo "   systemctl enable calbol celery"
echo "   systemctl start calbol celery"
echo ""
echo "8. Set up SSL (after pointing domain to server):"
echo "   apt install certbot python3-certbot-nginx"
echo "   certbot --nginx -d yourdomain.com"
echo ""
echo "=========================================="
echo "Setup script complete!"
echo "=========================================="
