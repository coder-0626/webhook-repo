from flask import Flask, request, jsonify, render_template
from pymongo import MongoClient
from datetime import datetime
import os
import logging
import json

app = Flask(__name__)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# MongoDB connection (local or Atlas)
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/github_events")
client = MongoClient(MONGO_URI)
db = client.get_database()
events = db.events

@app.route('/webhook', methods=['POST'])
def handle_webhook():
    try:
        # 1. Check if request is JSON
        if not request.is_json:
            logger.error("⚠️ Not a JSON request")
            return jsonify({"error": "Content-Type must be application/json"}), 400

        # 2. Get GitHub event type (push, pull_request, etc.)
        event_type = request.headers.get('X-GitHub-Event')
        if not event_type:
            logger.error("❌ Missing X-GitHub-Event header")
            return jsonify({"error": "Missing GitHub event type"}), 400

        data = request.get_json()
        logger.info(f"📦 Received {event_type} event:\n{json.dumps(data, indent=2)}")

        # 3. Process event based on type
        event = None

        # Push event
        if event_type == 'push':
            event = {
                "request_id": data.get('after', 'N/A'),
                "author": data.get('pusher', {}).get('name', 'unknown'),
                "action": "PUSH",
                "from_branch": data.get('ref', 'refs/heads/main').split('/')[-1],
                "to_branch": data.get('ref', 'refs/heads/main').split('/')[-1],
                "timestamp": datetime.utcnow().isoformat()
            }

        # Pull Request or Merge event
        elif event_type == 'pull_request':
            pr = data.get('pull_request', {})
            if data.get('action') == 'closed' and pr.get('merged'):
                # Merge event
                event = {
                    "request_id": str(pr.get('number', 'N/A')),
                    "author": pr.get('merged_by', {}).get('login', 'unknown'),
                    "action": "MERGE",
                    "from_branch": pr.get('head', {}).get('ref', 'unknown'),
                    "to_branch": pr.get('base', {}).get('ref', 'unknown'),
                    "timestamp": datetime.utcnow().isoformat()
                }
            else:
                # Pull Request event
                event = {
                    "request_id": str(pr.get('number', 'N/A')),
                    "author": pr.get('user', {}).get('login', 'unknown'),
                    "action": "PULL_REQUEST",
                    "from_branch": pr.get('head', {}).get('ref', 'unknown'),
                    "to_branch": pr.get('base', {}).get('ref', 'unknown'),
                    "timestamp": datetime.utcnow().isoformat()
                }

        # Unsupported event
        if not event:
            logger.error(f"❌ Unsupported event: {event_type}")
            return jsonify({"error": f"Unsupported event: {event_type}"}), 400

        # 4. Save to MongoDB
        events.insert_one(event)
        logger.info("✅ Event saved to MongoDB")

        return jsonify({"status": "success"}), 200

    except Exception as e:
        logger.error(f"🔥 Webhook failed: {str(e)}", exc_info=True)
        return jsonify({"error": "Server error"}), 500

@app.route('/api/events', methods=['GET'])
def get_events():
    try:
        latest_events = list(events.find().sort("timestamp", -1).limit(10))
        for event in latest_events:
            event["_id"] = str(event["_id"])
        return jsonify(latest_events)
    except Exception as e:
        logger.error(f"❌ Failed to fetch events: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
