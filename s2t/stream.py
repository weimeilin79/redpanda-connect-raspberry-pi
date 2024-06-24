import pyaudio
import soundfile as sf
import numpy as np
import threading
from faster_whisper import WhisperModel
from paho.mqtt import client as mqtt_client

# Parameters
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 8000
CHUNK = 1024
DEVICE_INDEX = 4  # Adjust this based on the output of arecord -l

#MQTT Parameters
MQTT_BROKER = "localhost"  
MQTT_PORT = 1883
MQTT_TOPIC = "transcription"
MQTT_CLIENT_ID = "raspberry_transcriber"


recording = False
stop_event = threading.Event()
frames = []
model = WhisperModel("tiny.en")

def record_audio(stop_event):
    global frames
    audio = pyaudio.PyAudio()
    device_info = audio.get_device_info_by_index(DEVICE_INDEX)
    print(f"Using device: {device_info['name']}")
    stream = audio.open(format=FORMAT, channels=CHANNELS,
                        rate=RATE, input=True,
                        input_device_index=DEVICE_INDEX,
                        frames_per_buffer=CHUNK)
    frames = []
    
    try:
        while not stop_event.is_set():
            data = stream.read(CHUNK)
            frames.append(data)
    except Exception as e:
        print(f"Error during recording: {e}")
    finally:
        stream.stop_stream()
        stream.close()
        audio.terminate()


def save_audio(frames, filename):
    print("Processing audio...", end="", flush=True)
    audio_data = b''.join(frames)
    audio_array = np.frombuffer(audio_data, dtype=np.int16)
    sf.write(filename, audio_array, RATE, format='FLAC')
    print("done.")

def transcribe_audio(client, filename):
    print("Transcribing audio...", end="", flush=True)
    segments, info = model.transcribe(filename, word_timestamps=False)
    full_text = ""
    for segment in segments:
        print("[%.2fs -> %.2fs] %s" % (segment.start, segment.end, segment.text))
        result = client.publish(MQTT_TOPIC, segment.text)
        status = result[0]
        if status == 0:
            print(f"Sent `{segment.text}` to topic `{MQTT_TOPIC}`")
        else:
            print(f"Failed to send message to topic {MQTT_TOPIC}")
        full_text += segment.text + " "  # Add a space between each segment for readability
    # Strip any trailing whitespace from the final concatenated string
    full_text = full_text.strip()
    print("Full Text:", full_text)

def on_connect(client, userdata, flags, rc, props=None):
    print("MQTT Broker Connected with result code " + str(rc))

if __name__ == "__main__":

    # Set up MQTT client
    client = mqtt_client.Client(mqtt_client.CallbackAPIVersion.VERSION2, MQTT_CLIENT_ID, clean_session=False, userdata=None)
    client.on_connect = on_connect
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    

    try:
        while True:
            print("Enter 's' to start recording, 'e' to stop recording, 'q' to exit program: ")
            command = input("Enter 's' to start recording, 'e' to stop recording: ")
            if command == 's' and not recording:
                recording = True
                stop_event.clear()
                print("Starting recording...")
                threading.Thread(target=record_audio, args=(stop_event,)).start()
            elif command == 'e' and recording:
                recording = False
                stop_event.set()
                print("Stopping recording...")
                filename = 'output.flac'
                save_audio(frames, filename)
                client.loop_start()
                transcribe_audio(client,filename)
                client.loop_stop()
            elif command == 'q':
                stop_event.set()
                print("Exiting program...")
                break

        
    except KeyboardInterrupt:
        if recording:
            stop_event.set()
        print("Gracefully shutting down...")