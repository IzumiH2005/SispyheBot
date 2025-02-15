import logging
import os
import signal
import sys
import json
import psutil
import time
from flask import Flask, jsonify
from datetime import datetime, timedelta

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

# Configuration
MAX_MEMORY_PERCENT = float(os.getenv('MAX_MEMORY_PERCENT', '85.0'))  # % maximum de mémoire utilisée
MAX_CPU_PERCENT = float(os.getenv('MAX_CPU_PERCENT', '80.0'))  # % maximum de CPU utilisé
ACTIVITY_THRESHOLD = int(os.getenv('ACTIVITY_THRESHOLD', '300'))  # 5 minutes en secondes

def check_bot_process():
    """Vérifie si le processus du bot est en cours d'exécution avec monitoring amélioré"""
    try:
        # Vérifie le fichier PID
        pid_file = "/tmp/telegram_bot.pid"
        if not os.path.exists(pid_file):
            return False, "PID file not found", {}

        with open(pid_file, 'r') as f:
            pid = int(f.read().strip())

        # Vérifie si le processus existe et collecte des métriques détaillées
        process = psutil.Process(pid)
        if not process.is_running():
            return False, "Bot process not found", {}

        # Collecte des métriques détaillées
        metrics = {
            'cpu_percent': process.cpu_percent(),
            'memory_percent': process.memory_percent(),
            'memory_info': {
                'rss': process.memory_info().rss / 1024 / 1024,  # MB
                'vms': process.memory_info().vms / 1024 / 1024   # MB
            },
            'num_threads': process.num_threads(),
            'connections': len(process.connections()),
            'open_files': len(process.open_files()),
            'status': process.status(),
            'create_time': datetime.fromtimestamp(process.create_time()).isoformat(),
            'uptime': str(timedelta(seconds=int(time.time() - process.create_time())))
        }

        # Vérification de l'activité récente via le fichier de log
        log_file = 'bot.log'
        if os.path.exists(log_file):
            last_modified = datetime.fromtimestamp(os.path.getmtime(log_file))
            time_since_last_activity = (datetime.now() - last_modified).total_seconds()
            metrics['last_activity'] = {
                'timestamp': last_modified.isoformat(),
                'seconds_ago': time_since_last_activity
            }

            if time_since_last_activity > ACTIVITY_THRESHOLD:
                return True, "Bot process is running but inactive", metrics

        # Vérifications des seuils critiques
        if metrics['memory_percent'] > MAX_MEMORY_PERCENT:
            return True, f"Memory usage critical: {metrics['memory_percent']:.1f}%", metrics

        if metrics['cpu_percent'] > MAX_CPU_PERCENT:
            return True, f"CPU usage critical: {metrics['cpu_percent']:.1f}%", metrics

        return True, "Bot process is running normally", metrics

    except Exception as e:
        return False, f"Error checking bot process: {str(e)}", {}

@app.route('/health')
def health_check():
    """Endpoint pour vérifier l'état du service avec monitoring amélioré"""
    try:
        # Vérification du processus du bot
        bot_running, bot_status, metrics = check_bot_process()

        # Métriques système globales
        system_metrics = {
            'system': {
                'cpu_percent': psutil.cpu_percent(),
                'memory_percent': psutil.virtual_memory().percent,
                'disk_usage': psutil.disk_usage('/').percent,
                'boot_time': datetime.fromtimestamp(psutil.boot_time()).isoformat(),
                'load_avg': os.getloadavg()
            }
        }

        # Combiner les métriques
        metrics.update(system_metrics)

        status = {
            'status': 'healthy' if bot_running else 'unhealthy',
            'timestamp': datetime.now().isoformat(),
            'bot_status': bot_status,
            'metrics': metrics,
            'warnings': []
        }

        # Ajouter des avertissements si nécessaire
        if bot_running:
            if metrics['memory_percent'] > MAX_MEMORY_PERCENT * 0.8:  # 80% du seuil critique
                status['warnings'].append(f"High memory usage: {metrics['memory_percent']:.1f}%")
            if metrics['cpu_percent'] > MAX_CPU_PERCENT * 0.8:
                status['warnings'].append(f"High CPU usage: {metrics['cpu_percent']:.1f}%")
            if metrics.get('last_activity', {}).get('seconds_ago', 0) > ACTIVITY_THRESHOLD * 0.8:
                status['warnings'].append("Bot activity is low")

        status_code = 200 if bot_running and not status['warnings'] else 503
        logger.info(f"Health check status: {json.dumps(status)}")
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
        'version': '1.1',
        'description': 'Service de surveillance pour le bot Sisyphe',
        'endpoints': {
            '/': 'Cette information',
            '/health': 'État détaillé du service avec métriques'
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
        port = int(os.getenv('PORT', 5001))
        logger.info(f"Starting health check server on port {port}")
        app.run(host='0.0.0.0', port=port, debug=False)
    except Exception as e:
        logger.error(f"Critical error in health check: {str(e)}")
        sys.exit(1)