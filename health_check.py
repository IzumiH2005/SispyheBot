import logging
import os
import signal
import sys
import json
import psutil
from flask import Flask, jsonify
from datetime import datetime

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

def check_bot_process():
    """Vérifie si le processus du bot est en cours d'exécution"""
    try:
        # Vérifie le fichier PID
        pid_file = "/tmp/telegram_bot.pid"
        if not os.path.exists(pid_file):
            return False, "PID file not found"

        with open(pid_file, 'r') as f:
            pid = int(f.read().strip())

        # Vérifie si le processus existe
        process = psutil.Process(pid)
        if process.is_running():
            return True, "Bot process is running"
        return False, "Bot process not found"
    except Exception as e:
        return False, f"Error checking bot process: {str(e)}"

@app.route('/health')
def health_check():
    """Endpoint pour vérifier l'état du service"""
    try:
        bot_running, bot_status = check_bot_process()

        status = {
            'status': 'healthy' if bot_running else 'unhealthy',
            'timestamp': datetime.now().isoformat(),
            'bot_status': bot_status,
            'memory_usage': psutil.Process().memory_info().rss / 1024 / 1024,  # MB
            'cpu_percent': psutil.Process().cpu_percent()
        }

        status_code = 200 if bot_running else 503
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
        port = int(os.getenv('PORT', 5001))  # Changed default port to 5001
        logger.info(f"Starting health check server on port {port}")
        app.run(host='0.0.0.0', port=port, debug=False)
    except Exception as e:
        logger.error(f"Critical error in health check: {str(e)}")
        sys.exit(1)