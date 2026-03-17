# Gunicorn configuration file
# https://docs.gunicorn.org/en/stable/settings.html

import multiprocessing

# Bind to Unix socket (nginx will connect to this)
bind = "unix:/var/www/calbol/calbol.sock"

# Number of worker processes
workers = multiprocessing.cpu_count() * 2 + 1

# Worker class
worker_class = "sync"

# Timeout for worker processes
timeout = 30

# Logging
accesslog = "/var/log/calbol/access.log"
errorlog = "/var/log/calbol/error.log"
loglevel = "info"

# Process naming
proc_name = "calbol"

# Daemonize (let systemd handle this)
daemon = False
