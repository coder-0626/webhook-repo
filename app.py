from flask import Flask, request, jsonify, render_template
from pymongo import MongoClient
from datetime import datetime
import os
import logging
import sys

app = Flask(__name__)

# Enhanced logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# MongoDB Connection with timeout and retry
def get_mongo_client():
    MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/github_events")
    try:
        client = MongoClient(
            MONGO_URI,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=30000,
            socketTimeoutMS=30000
        )
        # Verify connection immediately
        client.admin.command('ping')
        logger.info("✅ Successfully connected to MongoDB")
        return client
    except Exception as e:
        logger.error(f"❌ MongoDB connection failed: {str(e)}")
        raise

try:
    client = get_mongo_client()
    db = client.get_database()
    events = db.events
except Exception as e:
    logger.critical(f"Failed to initialize MongoDB: {str(e)}")
    sys.exit(1)

@app.route('/webhook', methods=['POST'])
def handle_webhook():
    """Enhanced webhook handler with complete error tracking"""
    try:
        logger.info("\n" + "="*40)
        logger.info("Incoming Webhook Request")
        logger.info(f"Headers: {dict(request.headers)}")
        
        # Validate JSON
        if not request.is_json:
            logger.error("Request is not JSON")
            return jsonify({"error": "Content-Type must be application/json"}), 400

        data = request.get_json()
        logger.info(f"Raw JSON Data:\n{json.dumps(data, indent=2)}")

        # Validate GitHub event type
        event_type = request.headers.get('X-GitHub-Event')
        if not event_type:
            logger.error("Missing X-GitHub-Event header")
            return jsonify({"error": "Missing GitHub event type"}), 400

        # Process different event types
        event = None
        
        if event_type == 'ping':
            logger.info("Received GitHub ping event")
            return jsonify({"status": "pong"}), 200

        elif event_type == 'push':
            event = {
                "request_id": data.get('after', 'N/A'),
                "author": data.get('pusher', {}).get('name', 'unknown'),
                "action": "PUSH",
                "from_branch": data.get('ref', 'refs/heads/main').split('/')[-1],
                "to_branch": data.get('ref', 'refs/heads/main').split('/')[-1],
                "timestamp": datetime.utcnow().isoformat()
            }

        elif event_type == 'pull_request':
            pr_data = data.get('pull_request', {})
            if data.get('action') == 'closed' and pr_data.get('merged'):
                event = {
                    "request_id": str(pr_data.get('number', 'N/A')),
                    "author": pr_data.get('merged_by', {}).get('login', 'unknown'),
                    "action": "MERGE",
                    "from_branch": pr_data.get('head', {}).get('ref', 'unknown'),
                    "to_branch": pr_data.get('base', {}).get('ref', 'unknown'),
                    "timestamp": datetime.utcnow().isoformat()
                }
            else:
                event = {
                    "request_id": str(pr_data.get('number', 'N/A')),
                    "author": pr_data.get('user', {}).get('login', 'unknown'),
                    "action": "PULL_REQUEST",
                    "from_branch": pr_data.get('head', {}).get('ref', 'unknown'),
                    "to_branch": pr_data.get('base', {}).get('ref', 'unknown'),
                    "timestamp": datetime.utcnow().isoformat()
                }

        if not event:
            logger.error(f"Unsupported event type: {event_type}")
            return jsonify({"error": f"Unsupported event type: {event_type}"}), 400

        # MongoDB Insert with error handling
        try:
            result = events.insert_one(event)
            logger.info(f"Successfully stored event with ID: {result.inserted_id}")
            logger.info(f"Stored Event:\n{json.dumps(event, indent=2)}")
            return jsonify({"status": "success", "event_id": str(result.inserted_id)}), 200
        except Exception as db_error:
            logger.error(f"MongoDB insert failed: {str(db_error)}")
            return jsonify({"error": "Database operation failed"}), 500

    except Exception as e:
        logger.error(f"Unexpected error in webhook handler: {str(e)}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500

@app.route('/api/events', methods=['GET'])
def get_events():
    """Enhanced API endpoint with error handling"""
    try:
        latest_events = list(events.find().sort("timestamp", -1).limit(10))
        logger.info(f"Returning {len(latest_events)} events from MongoDB")
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
