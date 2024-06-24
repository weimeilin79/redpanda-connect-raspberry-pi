from flask import Flask, request, jsonify
import json
app = Flask(__name__)


@app.route('/assign', methods=['POST'])
def assign_topic():
    
    print("Received a request to assign a topic to a device")
    data = json.loads(request.data.decode('utf-8'))
    if not data or 'device_id' not in data:
        return jsonify({"error": "device_id is required"}), 400
    
    
    print("device_id:", data['device_id'])
    # Store the assignment 
    # Please implement your own logic to store and assigned topic for each device.
    
    # For demo purposes, we are assigning the same topic "responses" to every device.
    assigned_topic = "responses"
    # Print the payload before converting to JSON
    result = jsonify({"device_id": data['device_id'] ,"assigned_topic": assigned_topic})
    print("Response data:", result.data.decode('utf-8'))
    return result

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8081)
