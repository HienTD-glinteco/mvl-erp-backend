# EC2 Test Environment Deployment Guide

This document provides detailed instructions for setting up the test environment deployment on an EC2 server with nginx, supervisor, and gunicorn.

## Server Architecture

### Components
- **EC2 Instance**: Single server hosting the application
- **Nginx**: Web server for serving static files and reverse proxy
- **Gunicorn**: WSGI HTTP Server for Django application (port 8080)
- **Supervisor**: Process control system for managing gunicorn workers
- **PostgreSQL**: Database server
- **Redis**: Cache and message broker

### Directory Structure
```
/var/www/backend/
├── app/                    # Django application code
├── venv/                   # Python virtual environment
├── static/                 # Static files served by nginx
├── media/                  # Media files served by nginx
├── logs/                   # Application logs
└── config/                 # Configuration files
    ├── nginx/              # Nginx configuration
    ├── supervisor/         # Supervisor configuration
    └── gunicorn/          # Gunicorn configuration
```

## Server Setup Instructions

### 1. EC2 Instance Setup

```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Install required packages
sudo apt install -y python3 python3-pip python3-venv nginx supervisor postgresql redis-server git

# Install Poetry
curl -sSL https://install.python-poetry.org | python3 -
```

### 2. Application Setup

```bash
# Create application directory
sudo mkdir -p /var/www/backend
sudo chown $USER:$USER /var/www/backend
cd /var/www/backend

# Clone repository
git clone https://github.com/MaiVietLand/backend.git .

# Create virtual environment and install dependencies
python3 -m venv venv
source venv/bin/activate
poetry install --no-interaction --no-root
```

### 3. Nginx Configuration

Create `/etc/nginx/sites-available/backend`:

```nginx
server {
    listen 80;
    server_name api.mvl.glinteco.com;
    # Để ACME challenge chạy ổn, không redirect tất cả ở đây
    location / { return 404; }
}

# Upstream tới Gunicorn (Unix socket)
upstream maivietland-upstream {
    server unix:/home/ubuntu/maivietland/maivietland.sock;
}

server {
    listen 443 ssl;
    server_name api.mvl.glinteco.com;

    # Native ACME: tự động cấp & gia hạn chứng chỉ cho server_name này
    acme_certificate letsencrypt;     # có thể thêm key=rsa:2048 nếu muốn RSA

    # Lấy cert/key từ biến do module cung cấp
    ssl_certificate       $acme_certificate;
    ssl_certificate_key   $acme_certificate_key;
    ssl_certificate_cache max=2;

    # Proxy tới Django qua Gunicorn
    location / {
        proxy_read_timeout 600s;
        proxy_connect_timeout 175s;
        proxy_pass http://maivietland-upstream;
        proxy_redirect off;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Static & Media
    #location /static/ { alias /home/ubuntu/maivietland/erp/staticfiles/; access_log off; }
    #location /media/  { alias /home/ubuntu/maivietland/erp/media/;       access_log off; }

    client_max_body_size 50M;
}
```

Create `/etc/nginx/sites-available/backend-test`:

```nginx
server {
    listen 80;
    server_name your-test-domain.com;

    # Static files
    location /static/ {
        alias /var/www/backend/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # Media files
    location /media/ {
        alias /var/www/backend/media/;
        expires 30d;
    }

    # Reverse proxy to gunicorn
    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeout settings
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "no-referrer-when-downgrade" always;
    add_header Content-Security-Policy "default-src 'self' http: https: data: blob: 'unsafe-inline'" always;
}
```

Enable the site:
```bash
sudo ln -s /etc/nginx/sites-available/backend /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### 4. Gunicorn Configuration

Create `/var/www/backend/config/gunicorn/gunicorn.conf.py`:

```python
import multiprocessing

# Server socket
bind = "127.0.0.1:8080"
backlog = 2048

# Worker processes
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"
worker_connections = 1000
timeout = 30
keepalive = 2

# Restart workers after this many requests, with up to 50% jitter
max_requests = 1000
max_requests_jitter = 50

# Logging
errorlog = "/var/www/backend/logs/gunicorn-error.log"
accesslog = "/var/www/backend/logs/gunicorn-access.log"
loglevel = "info"

# Process naming
proc_name = "backend_gunicorn"

# Server mechanics
preload_app = True
pidfile = "/var/www/backend/logs/gunicorn.pid"
user = "www-data"
group = "www-data"
tmp_upload_dir = None

# SSL (if needed)
# keyfile = "/path/to/keyfile"
# certfile = "/path/to/certfile"
```

### 5. Supervisor Configuration

Create `/etc/supervisor/conf.d/backend.conf`:

```ini
; ============ GUNICORN ============
[program:maivietland-api]
directory=/home/ubuntu/maivietland/backend
command=/home/ubuntu/maivietland/backend/.venv/bin/gunicorn \
    --chdir /home/ubuntu/maivietland/backend \
    --bind unix:/home/ubuntu/backend/maivietland.sock \
    --workers 4 \
    --timeout 300 \
    --access-logfile - \
    --error-logfile - \
    wsgi:application
user=ubuntu
autostart=true
autorestart=true
stopasgroup=true
killasgroup=true
umask=007
stdout_logfile=/home/ubuntu/maivietland/logs/gunicorn.log
stderr_logfile=/home/ubuntu/maivietland/logs/gunicorn.err
stdout_logfile_maxbytes=50MB
stderr_logfile_maxbytes=10MB
stdout_logfile_backups=50
stderr_logfile_backups=10
environment=
    ENVIRONMENT="test",
    PYTHONPATH="/home/ubuntu/maivietland/backend:/home/ubuntu/maivietland/backend:$PYTHONPATH",
    PATH="/home/ubuntu/maivietland/backend/.venv/bin:/usr/bin:/bin"
```

Update supervisor:
```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start maivietland-api
```

### 6. Environment Variables

The environment configuration is now managed directly on the server, not through GitHub Actions secrets.

Copy the appropriate environment example file to `.env` in your application directory:

```bash
# For test environment
cd /home/ubuntu/maivietland/backend
cp config/env/test.env.example .env

# For staging environment
cp config/env/staging.env.example .env
```

Then edit the `.env` file with your actual values:

```bash
nano .env
```

Example test environment configuration:
```bash
ENVIRONMENT=test
DEBUG=false
SECRET_KEY=your-actual-test-secret-key
DATABASE_URL=******localhost:5432/backend_test
ALLOWED_HOSTS=api.mvl.glinteco.com
CACHE_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
SENTRY_DSN=your-actual-sentry-dsn
SENTRY_ENVIRONMENT=test
```

**Important**: The CI/CD pipeline no longer manages environment variables through GitHub Actions secrets. All environment configuration must be done directly on the server.

### 7. Database Setup

```bash
# Create database and user
sudo -u postgres psql
CREATE DATABASE backend_test;
CREATE USER backend WITH PASSWORD 'password';
GRANT ALL PRIVILEGES ON DATABASE backend_test TO backend;
\q

# Run migrations
cd /var/www/backend
source venv/bin/activate
ENVIRONMENT=test python manage.py migrate
```

### 8. Log Directory Setup

```bash
sudo mkdir -p /var/www/backend/logs
sudo chown www-data:www-data /var/www/backend/logs
sudo chmod 755 /var/www/backend/logs
```

## GitHub Secrets Configuration

Configure the following secrets in your GitHub repository for the test environment:

```
TEST_HOST=your-ec2-ip-or-domain
TEST_USERNAME=ubuntu  # or your EC2 user
TEST_SSH_KEY=-----BEGIN OPENSSH PRIVATE KEY-----
...your private key...
-----END OPENSSH PRIVATE KEY-----
TEST_SECRET_KEY=your-test-secret-key
TEST_DATABASE_URL=postgres://backend:password@localhost:5432/backend_test
TEST_ALLOWED_HOSTS=your-test-domain.com
TEST_CACHE_URL=redis://localhost:6379/0
TEST_CELERY_BROKER_URL=redis://localhost:6379/0
TEST_SENTRY_DSN=your-sentry-dsn
TEST_APP_URL=http://your-test-domain.com
```

## Deployment Process

The automated deployment process:

1. **Code Deployment**: Pull latest code from master branch
2. **Dependencies**: Install/update Python packages with Poetry
3. **Database**: Run database migrations
4. **Static Files**: Collect static files for nginx to serve
5. **Application Restart**: Restart gunicorn workers via supervisor
6. **Web Server**: Reload nginx configuration
7. **Background Tasks**: Restart celery workers and beat scheduler
8. **Health Check**: Verify application and static file serving

## Monitoring and Logs

### Log Files
- **Application**: `/var/www/backend/logs/supervisor.log`
- **Gunicorn Access**: `/var/www/backend/logs/gunicorn-access.log`
- **Gunicorn Errors**: `/var/www/backend/logs/gunicorn-error.log`
- **Celery Worker**: `/var/www/backend/logs/celery-worker.log`
- **Celery Beat**: `/var/www/backend/logs/celery-beat.log`
- **Nginx Access**: `/var/log/nginx/access.log`
- **Nginx Errors**: `/var/log/nginx/error.log`

### Useful Commands

```bash
# Check application status
sudo supervisorctl status

# Restart application
sudo supervisorctl restart backend:*

# Check nginx status
sudo nginx -t
sudo systemctl status nginx

# View logs
tail -f /var/www/backend/logs/supervisor.log
tail -f /var/log/nginx/error.log

# Manual deployment test
cd /var/www/backend
source venv/bin/activate
ENVIRONMENT=test python manage.py check
```

## Security Considerations

1. **Firewall**: Configure security groups to allow only necessary ports (80, 443, 22)
2. **SSL**: Implement HTTPS with Let's Encrypt or SSL certificate
3. **Database**: Restrict database access to localhost only
4. **User Permissions**: Run application as www-data user with minimal privileges
5. **Secrets**: Store sensitive data in GitHub Secrets, not in code
6. **Updates**: Regularly update system packages and dependencies

## Troubleshooting

### Common Issues

1. **Permission Errors**: Ensure www-data user has proper permissions
2. **Port Conflicts**: Verify port 8080 is available for gunicorn
3. **Static Files**: Check nginx configuration and file permissions
4. **Database Connection**: Verify PostgreSQL is running and accessible
5. **Redis Connection**: Ensure Redis is running for cache and Celery
