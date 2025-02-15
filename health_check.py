import logging
import os
import signal
import sys
import json
import psutil
from flask import Flask, jsonify
from datetime import datetime
import socket

# Configuration du logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('health_check.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Application Flask pour le health check
app = Flask(__name__)

def is_port_in_use(port):
    """Vérifie si un port est déjà utilisé"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(('0.0.0.0', port))
            return False
        except socket.error:
            return True

def get_bot_metrics():
    """Récupère les métriques détaillées du processus du bot"""
    try:
        pid_file = "/tmp/telegram_bot.pid"
        if not os.path.exists(pid_file):
            logger.warning("PID file not found")
            return None, "PID file not found"

        with open(pid_file, 'r') as f:
            pid = int(f.read().strip())

        try:
            process = psutil.Process(pid)
            if not process.is_running():
                logger.warning(f"Bot process {pid} not running")
                return None, "Bot process not running"

            metrics = {
                'pid': pid,
                'cpu_percent': process.cpu_percent(),
                'memory_percent': process.memory_percent(),
                'memory_info': {
                    'rss': process.memory_info().rss / 1024 / 1024,  # MB
                    'vms': process.memory_info().vms / 1024 / 1024   # MB
                },
                'threads': len(process.threads()),
                'status': process.status(),
                'create_time': datetime.fromtimestamp(process.create_time()).isoformat(),
                'running_time': datetime.now().timestamp() - process.create_time()
            }
            logger.info(f"Bot metrics collected successfully for PID {pid}")
            return metrics, "Bot process is healthy"
        except psutil.NoSuchProcess:
            logger.error(f"Process {pid} not found")
            return None, f"Bot process {pid} not found"
    except Exception as e:
        logger.error(f"Error getting bot metrics: {str(e)}")
        return None, f"Error getting bot metrics: {str(e)}"

def check_multiple_instances():
    """Vérifie s'il y a des instances multiples du bot"""
    bot_processes = []
    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if 'python' in proc.info['name'] and 'bot.py' in ' '.join(proc.info['cmdline'] or []):
                    bot_processes.append(proc.info['pid'])
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return len(bot_processes) > 1, bot_processes
    except Exception as e:
        logger.error(f"Error checking multiple instances: {str(e)}")
        return False, []

@app.route('/health')
def health_check():
    """Endpoint pour vérifier l'état du service"""
    try:
        metrics, status_message = get_bot_metrics()
        multiple_instances, bot_pids = check_multiple_instances()

        status = {
            'timestamp': datetime.now().isoformat(),
            'bot_status': status_message,
            'multiple_instances_detected': multiple_instances,
            'bot_processes': bot_pids,
            'system_metrics': {
                'cpu_percent': psutil.cpu_percent(),
                'memory_percent': psutil.virtual_memory().percent,
                'disk_usage': psutil.disk_usage('/').percent
            }
        }

        if metrics:
            status['bot_metrics'] = metrics
            status['status'] = 'healthy'
            status_code = 200
        else:
            status['status'] = 'unhealthy'
            status_code = 503

        if multiple_instances:
            status['warning'] = 'Multiple bot instances detected'
            logger.warning(f"Multiple bot instances detected: {bot_pids}")

        logger.info(f"Health check completed: {json.dumps(status)}")
        return jsonify(status), status_code

    except Exception as e:
        error_status = {
            'status': 'error',
            'message': str(e),
            'timestamp': datetime.now().isoformat()
        }
        logger.error(f"Error in health check: {str(e)}")
        return jsonify(error_status), 500

@app.route('/')
def root():
    """Endpoint racine avec des informations basiques"""
    return jsonify({
        'service': 'Sisyphe Bot Health Check',
        'version': '1.0',
        'endpoints': {
            '/': 'This information',
            '/health': 'Health check status'
        }
    })

def signal_handler(signum, frame):
    """Gestion gracieuse des signaux d'arrêt"""
    logger.info(f"Received signal {signum}. Shutting down...")
    sys.exit(0)

if __name__ == '__main__':
    # Enregistrement des gestionnaires de signaux
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        port = int(os.getenv('PORT', 5002))

        # Vérification de la disponibilité du port
        if is_port_in_use(port):
            alt_port = 5003
            logger.warning(f"Port {port} is in use, trying alternate port {alt_port}")
            if is_port_in_use(alt_port):
                logger.error("Both primary and alternate ports are in use")
                sys.exit(1)
            port = alt_port

        logger.info(f"Starting health check server on port {port}")
        app.run(host='0.0.0.0', port=port, threaded=True)
    except Exception as e:
        logger.error(f"Critical error in health check: {str(e)}")
        logger.exception("Stack trace:")
        sys.exit(1)