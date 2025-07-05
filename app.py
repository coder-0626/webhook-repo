from flask import Flask, request, jsonify, render_template
from pymongo import MongoClient
from datetime import datetime
import os
import logging
import json

app = Flask(__name__)

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# MongoDB Connection with error handling
try:
    client = MongoClient(
        "mongodb://localhost:27017/",
        serverSelectionTimeoutMS=5000,
        connectTimeoutMS=30000
    )
    # Force connection test
    client.admin.command('ping')
    db = client['github_events']
    events = db['events']
    logger.info("✅ MongoDB connected successfully")
except Exception as e:
    logger.error(f"❌ MongoDB connection failed: {str(e)}")
    raise

@app.route('/webhook', methods=['POST'])
def handle_webhook():
    try:
        logger.info("\n=== NEW WEBHOOK REQUEST ===")
        
        # 1. Validate request
        if not request.is_json:
            logger.error("Request is not JSON")
            return jsonify({"error": "JSON required"}), 400

        data = request.get_json()
        event_type = request.headers.get('X-GitHub-Event')
        
        logger.debug(f"Headers: {dict(request.headers)}")
        logger.debug(f"Event Type: {event_type}")
        logger.debug(f"Payload:\n{json.dumps(data, indent=2)}")

        # 2. Handle ping event
        if event_type == 'ping':
            logger.info("GitHub ping received")
            return jsonify({"status": "pong"}), 200

        # 3. Process supported events
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "github_event": event_type,
            "raw_data": data  # Store complete payload for debugging
        }

        if event_type == 'push':
            event.update({
                "request_id": data.get('after', 'N/A'),
                "author": data.get('pusher', {}).get('name', 'unknown'),
                "action": "PUSH",
                "from_branch": data.get('ref', 'refs/heads/main').split('/')[-1],
                "to_branch": data.get('ref', 'refs/heads/main').split('/')[-1]
            })
        elif event_type == 'pull_request':
            pr = data.get('pull_request', {})
            event.update({
                "request_id": str(pr.get('number', 'N/A')),
                "author": pr.get('user', {}).get('login', 'unknown'),
                "from_branch": pr.get('head', {}).get('ref', 'unknown'),
                "to_branch": pr.get('base', {}).get('ref', 'unknown'),
                "action": "MERGE" if data.get('action') == 'closed' and pr.get('merged') else "PULL_REQUEST"
            })

        # 4. Store in MongoDB with verification
        try:
            result = events.insert_one(event)
            logger.info(f"✅ Event saved with ID: {result.inserted_id}")
            
            # Verify the document exists
            if not events.find_one({"_id": result.inserted_id}):
                raise Exception("Write verification failed")
                
            return jsonify({"status": "success"}), 200
            
        except Exception as db_error:
            logger.error(f"❌ MongoDB write failed: {str(db_error)}")
            return jsonify({"error": "Database operation failed"}), 500

    except Exception as e:
        logger.error(f"🔥 Webhook processing failed: {str(e)}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500

@app.route('/api/events', methods=['GET'])
def get_events():
    try:
        latest_events = list(events.find().sort("timestamp", -1).limit(10))
        for event in latest_events:
            event["_id"] = str(event["_id"])
        return jsonify(latest_events)
    except Exception as e:
        logger.error(f"Failed to fetch events: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
