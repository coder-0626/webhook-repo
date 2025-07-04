from flask import Flask, request, jsonify, render_template
from pymongo import MongoClient
from datetime import datetime
import os
import logging

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
    try:
        # Verify content type
        if request.content_type != 'application/json':
            logger.error(f"Invalid content type: {request.content_type}")
            return jsonify({"error": "Content-Type must be application/json"}), 400

        data = request.get_json()
        if not data:
            logger.error("No JSON data received")
            return jsonify({"error": "No JSON data received"}), 400

        # Get GitHub event type from headers
        event_type = request.headers.get('X-GitHub-Event')
        logger.info(f"Received GitHub event: {event_type}")

        # Process different event types
        if event_type == 'push':
            # Push event
            event = {
                "request_id": data.get('after'),
                "author": data.get('pusher', {}).get('name'),
                "action": "PUSH",
                "from_branch": data.get('ref', '').split('/')[-1],
                "to_branch": data.get('ref', '').split('/')[-1],
                "timestamp": datetime.utcnow().isoformat()
            }
        elif event_type == 'pull_request':
            # Pull Request event
            pr_data = data.get('pull_request', {})
            if data.get('action') == 'closed' and pr_data.get('merged'):
                # Merge event
                event = {
                    "request_id": str(pr_data.get('number')),
                    "author": pr_data.get('merged_by', {}).get('login'),
                    "action": "MERGE",
                    "from_branch": pr_data.get('head', {}).get('ref'),
                    "to_branch": pr_data.get('base', {}).get('ref'),
                    "timestamp": datetime.utcnow().isoformat()
                }
            else:
                # Regular PR event
                event = {
                    "request_id": str(pr_data.get('number')),
                    "author": pr_data.get('user', {}).get('login'),
                    "action": "PULL_REQUEST",
                    "from_branch": pr_data.get('head', {}).get('ref'),
                    "to_branch": pr_data.get('base', {}).get('ref'),
                    "timestamp": datetime.utcnow().isoformat()
                }
        else:
            logger.warning(f"Unsupported event type: {event_type}")
            return jsonify({"error": f"Unsupported event type: {event_type}"}), 400

        # Insert into MongoDB
        result = events.insert_one(event)
        logger.info(f"Inserted event with ID: {result.inserted_id}")

        return jsonify({"status": "success", "event_id": str(result.inserted_id)}), 200

    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}", exc_info=True)
        return jsonify({"error": "Internal server error", "details": str(e)}), 500

@app.route('/api/events', methods=['GET'])
def get_events():
    try:
        latest_events = list(events.find().sort("timestamp", -1).limit(10))
        for event in latest_events:
            event["_id"] = str(event["_id"])
        return jsonify(latest_events)
    except Exception as e:
        logger.error(f"Error fetching events: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
