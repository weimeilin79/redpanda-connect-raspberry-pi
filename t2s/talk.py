from paho.mqtt import client as mqtt_client
from espeak import espeak



espeak.speed = 300
espeak.voice = "en-us+f4"

# Define the callback function for when a message is received
def on_message(client, userdata, message):
    print(f"Received message from MQTT TOPIC: {message.payload.decode()}")
    espeak.synth(str({message.payload.decode()}))

MQTT_CLIENT_ID = "raspberry_talk"
# Create a new MQTT client instance
client = mqtt_client.Client(mqtt_client.CallbackAPIVersion.VERSION2, MQTT_CLIENT_ID, clean_session=False, userdata=None)

# Attach the on_message callback function to the client
client.on_message = on_message

# Connect to an MQTT broker
broker_address = "localhost"  # You can use any public broker or your own
port = 1883

client.connect(broker_address, port=port)

# Subscribe to the topic 'talk'
topic = "talk"
client.subscribe(topic)

# Start the MQTT client loop
client.loop_start()

# Keep the script running
try:
    while True:
        pass
except KeyboardInterrupt:
    client.loop_stop()
    client.disconnect()
    print("Disconnected from broker")
