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

# MongoDB Connection with Validation
try:
    client = MongoClient(
        os.getenv("MONGO_URI", "mongodb://localhost:27017/"),
        serverSelectionTimeoutMS=5000,
        connectTimeoutMS=30000
    )
    # Verify connection works
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
        logger.info("\n=== NEW WEBHOOK ===")
        
        # 1. Validate request
        if not request.is_json:
            logger.error("Request is not JSON")
            return jsonify({"error": "JSON required"}), 400

        event_type = request.headers.get('X-GitHub-Event')
        data = request.get_json()
        logger.info(f"Event Type: {event_type}")
        logger.debug(f"Full Payload:\n{json.dumps(data, indent=2)}")

        # 2. Process GitHub ping
        if event_type == 'ping':
            logger.info("GitHub ping received")
            return jsonify({"status": "pong"}), 200

        # 3. Handle supported events
        event = None
        if event_type == 'push':
            event = {
                "request_id": data.get('after', 'N/A'),
                "author": data.get('pusher', {}).get('name', 'unknown'),
                "action": "PUSH",
                "from_branch": data.get('ref', 'refs/heads/main').split('/')[-1],
                "to_branch": data.get('ref', 'refs/heads/main').split('/')[-1],
                "timestamp": datetime.utcnow().isoformat()
            }
        elif event_type == 'pull_request':
            pr = data.get('pull_request', {})
            if data.get('action') == 'closed' and pr.get('merged'):
                event = {
                    "request_id": str(pr.get('number', 'N/A')),
                    "author": pr.get('merged_by', {}).get('login', 'unknown'),
                    "action": "MERGE",
                    "from_branch": pr.get('head', {}).get('ref', 'unknown'),
                    "to_branch": pr.get('base', {}).get('ref', 'unknown'),
                    "timestamp": datetime.utcnow().isoformat()
                }
            else:
                event = {
                    "request_id": str(pr.get('number', 'N/A')),
                    "author": pr.get('user', {}).get('login', 'unknown'),
                    "action": "PULL_REQUEST",
                    "from_branch": pr.get('head', {}).get('ref', 'unknown'),
                    "to_branch": pr.get('base', {}).get('ref', 'unknown'),
                    "timestamp": datetime.utcnow().isoformat()
                }

        if not event:
            logger.error(f"Unsupported event: {event_type}")
            return jsonify({"error": "Unsupported event type"}), 400

        # 4. Store in MongoDB with validation
        try:
            result = events.insert_one(event)
            logger.info(f"✅ Event saved to MongoDB with ID: {result.inserted_id}")
            logger.debug(f"Stored Event:\n{json.dumps(event, indent=2)}")
            
            # Verify write
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
        logger.info(f"Returning {len(latest_events)} events")
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
