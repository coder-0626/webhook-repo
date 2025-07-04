from flask import Flask, request, jsonify, render_template
from pymongo import MongoClient
from datetime import datetime
import os

app = Flask(__name__)

# MongoDB Connection
MONGO_URI = os.getenv("MONGO_URI")  # Store in .env
client = MongoClient(MONGO_URI)
db = client.github_events
events = db.events

@app.route('/webhook', methods=['POST'])
def handle_webhook():
    data = request.json

    # GitHub Push Event
    if 'pusher' in data:
        event = {
            "request_id": data['after'],
            "author": data['pusher']['name'],
            "action": "PUSH",
            "from_branch": data['ref'].split('/')[-1],
            "to_branch": data['ref'].split('/')[-1],
            "timestamp": datetime.utcnow().isoformat()
        }

    # GitHub Pull Request Event
    elif 'pull_request' in data:
        event = {
            "request_id": str(data['pull_request']['number']),
            "author": data['pull_request']['user']['login'],
            "action": "PULL_REQUEST",
            "from_branch": data['pull_request']['head']['ref'],
            "to_branch": data['pull_request']['base']['ref'],
            "timestamp": datetime.utcnow().isoformat()
        }

    # GitHub Merge Event (Brownie Points)
    elif 'pull_request' in data and data['action'] == 'closed' and data['pull_request']['merged']:
        event = {
            "request_id": str(data['pull_request']['number']),
            "author": data['pull_request']['merged_by']['login'],
            "action": "MERGE",
            "from_branch": data['pull_request']['head']['ref'],
            "to_branch": data['pull_request']['base']['ref'],
            "timestamp": datetime.utcnow().isoformat()
        }

    else:
        return jsonify({"status": "Unsupported event"}), 400

    # Save to MongoDB
    events.insert_one(event)
    return jsonify({"status": "Success"}), 200

@app.route('/')
def home():
    return render_template("index.html")

@app.route('/api/events')
def get_events():
    latest_events = list(events.find().sort("timestamp", -1).limit(10))
    for event in latest_events:
        event["_id"] = str(event["_id"])  # Convert ObjectId to string
    return jsonify(latest_events)

if __name__ == '__main__':
    app.run(debug=True)