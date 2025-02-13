import logging
from flask import Flask, jsonify
import requests
from config import TELEGRAM_TOKEN
import os

# Configuration du logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Application Flask pour le health check
app = Flask(__name__)

def check_telegram_connection():
    """Vérifie la connexion avec l'API Telegram via une simple requête HTTP"""
    try:
        response = requests.get(f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/getMe')
        if response.status_code == 200:
            bot_info = response.json()
            if bot_info.get('ok'):
                return True, f"Connected as @{bot_info['result']['username']}"
        return False, "Failed to connect to Telegram API"
    except Exception as e:
        return False, str(e)

@app.route('/')
def root():
    """Route racine qui redirige vers le health check"""
    return jsonify({'status': 'ok', 'message': 'Use /health for status check'})

@app.route('/health')
def health_check():
    """Endpoint de health check"""
    try:
        is_connected, message = check_telegram_connection()
        if is_connected:
            return jsonify({'status': 'healthy', 'telegram_bot': message}), 200
        return jsonify({'status': 'unhealthy', 'error': message}), 503
    except Exception as e:
        logger.error(f"Health check error: {str(e)}")
        return jsonify({'status': 'error', 'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.getenv('PORT', 8080))
    app.run(host='0.0.0.0', port=port)