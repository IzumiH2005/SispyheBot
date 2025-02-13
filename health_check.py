import logging
from flask import Flask, jsonify
import os

# Configuration du logging (removed Telegram-specific logging)
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Application Flask pour le health check
app = Flask(__name__)

@app.route('/health')
def health_check():
    return jsonify({'status': 'healthy'}), 200

@app.route('/')
def root():
    return jsonify({'message': 'API is running. Use /health for health check'})

if __name__ == '__main__':
    port = int(os.getenv('PORT', 8080))
    app.run(host='0.0.0.0', port=port)