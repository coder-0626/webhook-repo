from flask import Flask, request, jsonify, render_template
from pymongo import MongoClient
from datetime import datetime
import os
import logging
import json

app = Flask(__name__)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# MongoDB Connection (verified working)
client = MongoClient("mongodb://localhost:27017/")
db = client['github_events']
events = db['events']

@app.route('/webhook', methods=['POST'])
def handle_webhook():
    try:
        # Validate JSON
        if not request.is_json:
            return jsonify({"error": "JSON required"}), 400

        data = request.get_json()
        event_type = request.headers.get('X-GitHub-Event')

        # Process events
        if event_type == 'ping':
            return jsonify({"status": "pong"}), 200

        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "github_event": event_type
        }

        if event_type == 'push':
            event.update({
                "request_id": data.get('after'),
                "author": data.get('pusher', {}).get('name'),
                "action": "PUSH",
                "from_branch": data.get('ref', 'refs/heads/main').split('/')[-1],
                "to_branch": data.get('ref', 'refs/heads/main').split('/')[-1]
            })
        elif event_type == 'pull_request':
            pr = data.get('pull_request', {})
            event.update({
                "request_id": str(pr.get('number')),
                "author": pr.get('user', {}).get('login'),
                "from_branch": pr.get('head', {}).get('ref'),
                "to_branch": pr.get('base', {}).get('ref'),
                "action": "MERGE" if data.get('action') == 'closed' and pr.get('merged') else "PULL_REQUEST"
            })

        # Insert into MongoDB
        events.insert_one(event)
        return jsonify({"status": "success"}), 200

    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/api/events', methods=['GET'])
def get_events():
    try:
        latest_events = list(events.find().sort("timestamp", -1).limit(10))
        for event in latest_events:
            event["_id"] = str(event["_id"])
        return jsonify(latest_events)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
