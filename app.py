from flask import Flask, request, jsonify, render_template
from pymongo import MongoClient
from datetime import datetime
import os
import logging
import json

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# MongoDB Connection
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/github_events")
client = MongoClient(MONGO_URI)
db = client.get_database()
events = db.events

@app.route('/webhook', methods=['POST'])
def handle_webhook():
    """Endpoint for GitHub webhooks"""
    try:
        # Verify JSON content
        if not request.is_json:
            return jsonify({"error": "JSON required"}), 400

        event_type = request.headers.get('X-GitHub-Event')
        data = request.get_json()

        # Handle ping event (webhook setup test)
        if event_type == 'ping':
            return jsonify({"status": "pong"}), 200

        # Process supported events
        event = None
        if event_type == 'push':
            event = {
                "request_id": data.get('after'),
                "author": data.get('pusher', {}).get('name'),
                "action": "PUSH",
                "from_branch": data.get('ref', '').split('/')[-1],
                "to_branch": data.get('ref', '').split('/')[-1],
                "timestamp": datetime.utcnow().isoformat()
            }
        elif event_type == 'pull_request':
            pr = data.get('pull_request', {})
            if data.get('action') == 'closed' and pr.get('merged'):
                event = {
                    "request_id": str(pr.get('number')),
                    "author": pr.get('merged_by', {}).get('login'),
                    "action": "MERGE",
                    "from_branch": pr.get('head', {}).get('ref'),
                    "to_branch": pr.get('base', {}).get('ref'),
                    "timestamp": datetime.utcnow().isoformat()
                }
            else:
                event = {
                    "request_id": str(pr.get('number')),
                    "author": pr.get('user', {}).get('login'),
                    "action": "PULL_REQUEST",
                    "from_branch": pr.get('head', {}).get('ref'),
                    "to_branch": pr.get('base', {}).get('ref'),
                    "timestamp": datetime.utcnow().isoformat()
                }

        if not event:
            return jsonify({"error": "Unsupported event"}), 400

        # Store in MongoDB
        events.insert_one(event)
        return jsonify({"status": "success"}), 200

    except Exception as e:
        logger.error(f"Webhook error: {str(e)}")
        return jsonify({"error": "Server error"}), 500

@app.route('/api/events', methods=['GET'])
def get_events():
    """API endpoint for UI to fetch latest events"""
    try:
        latest_events = list(events.find().sort("timestamp", -1).limit(10))
        for event in latest_events:
            event["_id"] = str(event["_id"])
        return jsonify(latest_events)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/')
def index():
    """Serve the UI dashboard"""
    return render_template('index.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)