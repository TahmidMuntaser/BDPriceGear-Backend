# Gunicorn configuration file
import multiprocessing
import os

# Server Socket
bind = f"0.0.0.0:{os.environ.get('PORT', '8000')}"
backlog = 2048

# Worker Processes
workers = int(os.environ.get('GUNICORN_WORKERS', multiprocessing.cpu_count() * 2 + 1))
worker_class = 'sync'
worker_connections = 1000
max_requests = 1000  # Restart workers after this many requests to prevent memory leaks
max_requests_jitter = 50  # Add randomness to prevent all workers restarting at once
timeout = 300  # 5 minutes for long-running requests
graceful_timeout = 30  # 30 seconds for graceful shutdown
keepalive = 5  # Keep connections alive for 5 seconds

# Server Mechanics
daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

# Logging
accesslog = '-'  # Log to stdout
errorlog = '-'  # Log to stderr
loglevel = 'info'
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = 'bdpricegear-backend'

# Server hooks
def on_starting(server):
    """Called just before the master process is initialized."""
    server.log.info("Starting BDPriceGear Backend server...")

def on_reload(server):
    """Called to recycle workers during a reload via SIGHUP."""
    server.log.info("Reloading workers...")

def when_ready(server):
    """Called just after the server is started."""
    server.log.info("Server is ready. Spawning workers")

def pre_fork(server, worker):
    """Called just before a worker is forked."""
    pass

def post_fork(server, worker):
    """Called just after a worker has been forked."""
    server.log.info(f"Worker spawned (pid: {worker.pid})")

def pre_exec(server):
    """Called just before a new master process is forked."""
    server.log.info("Forked child, re-executing.")

def worker_int(worker):
    """Called when a worker receives the SIGINT or SIGQUIT signal."""
    worker.log.info(f"Worker received INT or QUIT signal (pid: {worker.pid})")

def worker_abort(worker):
    """Called when a worker receives the SIGABRT signal."""
    worker.log.info(f"Worker received SIGABRT signal (pid: {worker.pid})")

def post_worker_init(worker):
    """Called just after a worker has initialized the application."""
    from django.db import close_old_connections
    # Close any database connections from the parent process
    close_old_connections()
    worker.log.info(f"Worker initialized (pid: {worker.pid})")

def worker_exit(server, worker):
    """Called just after a worker has been exited."""
    from django.db import close_old_connections
    # Close database connections when worker exits
    close_old_connections()
    server.log.info(f"Worker exiting (pid: {worker.pid})")

def child_exit(server, worker):
    """Called just after a worker has been exited, in the master process."""
    server.log.info(f"Worker child exited (pid: {worker.pid})")

def on_exit(server):
    """Called just before exiting Gunicorn."""
    server.log.info("Shutting down BDPriceGear Backend server...")
