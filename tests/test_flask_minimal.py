#!/usr/bin/env python3
# Test minimal Flask app to isolate the problem

from flask import Flask
import sys
import os

# Add the project directory to path for imports
sys.path.insert(0, os.path.dirname(__file__))

app = Flask(__name__)

@app.route("/ping")
def ping():
    return "pong", 200

@app.route("/")
def home():
    return "Flask is working!", 200

if __name__ == "__main__":
    print("Starting minimal Flask...")
    print("URLs:")
    print("- http://127.0.0.1:5000/ping")
    print("- http://127.0.0.1:5000/")
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)