from flask import Flask, request, jsonify
from pymongo import MongoClient
from datetime import datetime
import os
import logging

app = Flask(__name__)

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# MongoDB Connection (Local / Atlas)
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/github_events")
client = MongoClient(MONGO_URI)
db = client.get_database()
events = db.events

@app.route('/webhook', methods=['POST'])
def handle_webhook():
    try:
        # 1. Check if request is JSON
        if not request.is_json:
            logger.error("❌ Not JSON")
            return jsonify({"error": "Send JSON data"}), 400

        # 2. Get GitHub event type (push/pull_request)
        event_type = request.headers.get('X-GitHub-Event')
        if not event_type:
            logger.error("❌ Missing GitHub event header")
            return jsonify({"error": "X-GitHub-Event header missing"}), 400

        data = request.get_json()
        logger.info(f"📦 Event Type: {event_type}")

        # 3. Process based on event type
        if event_type == 'push':
            # Push event
            event = {
                "request_id": data.get('after', 'N/A'),
                "author": data.get('pusher', {}).get('name', 'unknown'),
                "action": "PUSH",
                "from_branch": data.get('ref', '').split('/')[-1],
                "to_branch": data.get('ref', '').split('/')[-1],
                "timestamp": datetime.utcnow().isoformat()
            }
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
        else:
            logger.error(f"❌ Unsupported event: {event_type}")
            return jsonify({"error": "Unsupported event"}), 400

        # 4. Save to MongoDB
        events.insert_one(event)
        logger.info("✅ Saved to MongoDB")
        return jsonify({"status": "success"}), 200

    except Exception as e:
        logger.error(f"🔥 Error: {str(e)}")
        return jsonify({"error": "Server error"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
