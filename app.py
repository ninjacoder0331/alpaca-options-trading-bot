from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

@app.route('/')
def home():
    return jsonify({
        "message": "Welcome to the Flask API",
        "status": "success"
    })

@app.route('/api/health')
def health_check():
    return jsonify({
        "status": "healthy",
        "port": 5000
    })

@app.route('/api/data', methods=['POST'])
def handle_post():
    data = request.get_json()
    return jsonify({
        "message": "Data received successfully",
        "received_data": data,
        "status": "success"
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000) 