# Gunicorn configuration for low-memory production deployment
# Optimized for 512MB-1GB RAM instances

import os
import multiprocessing

# Server socket
bind = f"0.0.0.0:{os.getenv('PORT', '5000')}"
backlog = 64

# Worker processes
# For 512MB: Use 1 worker
# For 1GB: Use 2 workers
workers = int(os.getenv('GUNICORN_WORKERS', '1'))
worker_class = 'sync'
worker_connections = 50
max_requests = 100  # Restart worker after N requests to prevent memory leaks
max_requests_jitter = 10  # Add randomness to prevent all workers restarting at once
timeout = 120  # Timeout for requests (important for semantic search)
keepalive = 5

# Don't preload the app to save memory
# Each worker will load the app independently
preload_app = False

# Logging
accesslog = '-'  # Log to stdout
errorlog = '-'   # Log to stderr
loglevel = 'info'
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = 'pirkei_avot_app'

# Server mechanics
daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

# Memory optimization
# Restart workers if they exceed memory threshold (optional)
# Requires psutil: pip install psutil
def on_starting(server):
    """Called just before the master process is initialized."""
    server.log.info("Starting Pirkei Avot application")
    server.log.info(f"Workers: {workers}")
    server.log.info(f"Worker class: {worker_class}")

def worker_int(worker):
    """Called when a worker receives the SIGINT or SIGQUIT signal."""
    worker.log.info("Worker received INT or QUIT signal")

def worker_abort(worker):
    """Called when a worker receives the SIGABRT signal."""
    worker.log.info("Worker received SIGABRT signal")
