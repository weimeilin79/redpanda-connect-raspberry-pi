# Smart Robot Demo on Raspberry Pi 

This demo showcases a conversational robot built on a Raspberry Pi 4, transforming it into an interactive gadget capable of answering questions. The system leverages OpenAI for generating responses and utilizes Redpanda Connect for efficient data processing. The main inference work runs on a more powerful server, either local or cloud-based, while the Raspberry Pi handles real-time interaction with users. Despite its limited hardware resources, the edge device can efficiently manages speech-to-text conversion, communication with the central hub, and text-to-speech playback.

![Demo View](images/demoview.png)

Here is the video of the demo running: https://www.youtube.com/watch?v=8aJlImtFzn4

## High-Level Architecture

- Edge Device (Raspberry Pi 4)
    - **MQTT Server (Mosquitto)**: Manages communication between the microphone, the text-to-speech application, and the central hub.
    - **Stream Application (stream.py)**: Uses faster_whisper to transcribe speech into text, parses it into chunks, and sends them to the MQTT server.
    - **Talk Application (talk.py)**: Converts text back to speech and plays it through the speaker.
    - **Dynamic Topic Assignment (init.yaml)**: Uses Redpanda Connect, run when the edge device first boots, to get an assigned topic name for the device.
    - **Prompt Data Pipeline (edgepipe.yaml)**: Uses Redpanda Connect for lightweight, fast data transfer to the Redpanda Serverless Broker. It pre-processes and aggregates transcribed text chunks every 10 seconds, forming proper query sentences and sending them along with edge device info to the Redpanda Cluster.
    - **Response Data Pipeline (talkpipe.yaml)**: Uses Redpanda Connect to listen to the dynamically assigned topic, filters the answers that have the device ID, and sends them to the MQTT Server.

![Redpanda Connect pipeline](images/datapipelines.png)

- Central Hub
  - **Redpanda Serverless Broker**: Acts as the central messaging system, facilitating communication between the edge device and the inference server. (We are using Redpanda Serverless in this case)
  - **Inference RAG Program (inference.py)**: Processes incoming queries using document search with a vector database and generates accurate answers by interfacing with OpenAI.
  - **Dynamic Topic Assignment (assignment.py)**: Assigns topics to edge devices based on load to manage the number of topics efficiently. (Since this is a demo, we are just hardcoding the topic name, but in the real world, you should have a strategy of grouping devices based on load and locations.)

## Technologies Used
  - `Raspberry Pi 4`: Low-cost, single-board computer serving as the edge device.
  - `MQTT Server (Mosquitto)`: Lightweight messaging protocol for small sensors and mobile devices, optimized for high-latency or unreliable networks.
  - `Faster Whisper`: A lightweight model for real-time speech-to-text conversion.
  - `Redpanda Connect`: Runs on the edge device to manage lightweight and fast data transfer, pre-processing, and aggregation of transcribed text.
  - `Redpanda Serverless` : Central messaging system enabling efficient communication between devices and servers.
  - `Mongo Atlas`: Document Search with Vector Database, used by the RAG program to provide contextually accurate answers.
  - `OpenAI` : Generates responses based on the context provided by the document search.

## Workflow

![Workflow View](images/workflow.png)

- Dynamic Topic Assignment: 
  - When the edge device starts up, it sends a request to an API endpoint `assignment.py`.
  - The API dynamically assigns a topic based on the current load and sends the topic name back to the edge device, where it is stored locally `init.yaml`.

- Speech to Text: 
  - The user speaks into the microphone.
  - The` stream.py` application transcribes speech to text and sends chunks to the MQTT server.
  - Redpanda Connect `edgepipe.yaml` on the edge device aggregates text chunks every 10 seconds to form a complete query. The query, along with edge device information, is sent to the Redpanda Cluster.

- Answer Generation:
  - The RAG program `inference.py` processes the query and generates an answer using document search with a vector database and invoke the OpenAI model.
  - The answer is sent to the dynamically assigned topic for the edge device.

- Text to Speech:
    - The edge device `talkpipe.yaml` listens to the assigned topic for the answer, filters the input data to match the device ID, and sends it to the MQTT broker.
    - The `talk.py` application converts the text answer to speech and plays it through the speaker.


## Install & Deploy

### Redpanda Serverless
Sign up if you have not already done so.
- Create a new Serverless virtual cluster. 
- Make a note of the bootstrap server URL, 
- Create a new user with permissions (ACLs)
- Create topics `prompts` and `responses`

### Central Hub

Copy files under `local` folder
```
|
|-/local
```

Set environment variables
```
cd local
% cat > .env<< EOF
OPENAI_MODEL="gpt-4o"
OPENAI_API_KEY=<openai_key>
OPENAI_ORGANIZATION_ID=<openai_org_id>
OPENAI_EMBEDDING_MODE = "text-embedding-3-small"

MONGODB_URI = "<mongo_atlas_uri>"
DB_NAME = "<mongo_dbname>"
COLLECTION_NAME = "<collection name of vector store>"
INDEX_NAME = "<index in the collection>"

REDPANDA_SERVER=<bootstrap_server_url>
REDPANDA_USER=<username>
REDPANDA_PWD=<password>

EOF
export $(grep -v '^#' .env | xargs)
```


Install the python libraries to start the inference application
```
python3 -m venv env
pip install -r  requirements.txt
```

Start the inference application, it'll retrieve relevant doc from MongoDB, and use it with the query to invoke OpenAI model
```
source env/bin/activate
python3 inference.py
```

Start the assignment API service, that will tell edge which topic the response will send to:
```
python3 assignment.py
```


### Edge Device (Raspberry Pi 4)

- Operating System: Ubuntu:  24.04 LTS
- Python: 3.12
- Install Mosquitto: 2.0.18 
  - create `/etc/mosquitto/conf.d/mosquitto.conf` with following setting
```
listener 1883 0.0.0.0
allow_anonymous true
```
- Start the Mosquitto server

Install rpk 

```
curl -1sLf 'https://dl.redpanda.com/nzc4ZYQK3WRGd9sy/redpanda/cfg/setup/bash.deb.sh' | \
sudo -E bash && sudo apt install redpanda -y
```

Check and configure your microphone, where it will display the list of CAPTURE Hardware Devices
```
arecord -l
```

My audio device is on card 1
```
card 1: Device [USB PnP Sound Device], device 0: USB Audio [USB Audio]
....
```

Depends on your microphone setting, set your `/etc/asound.conf`

```
pcm.!default {
    type plug
    slave.pcm.type pipewire
}

ctl.!default {
    type hw
    card 1
}
```

Install the common libraries, some needs system level
```
sudo apt-get install espeak
sudo apt-get install python3-espeak
sudo apt-get install python3-paho-mqtt
```


Copy files under folder to your edge device
```
|
|-/s2t/streams.py
|-/t2s/talk.py
|-/connect/*.yaml
```

Set environment variables
```
cd connect/
% cat > .env<< EOF
ASSIGNMENT_HOST=<central_hub_ip_address:central_hub_api_port>
EDGE_HOST=<edge_ip_address>
REDPANDA_SERVER=<bootstrap_server_url>
REDPANDA_USERNAME=<username>
REDPANDA_PASSWORD=password>

EOF
export $(grep -v '^#' .env | xargs)
```


Run the init.yaml to get the assigned topic name (Make sure your assignment service in central hub is already up and running)

```
rpk connect run init.yaml
```


Start the pipeline that will pre-process data by aggregating chunks of transcribed data in a 30 second window time frame and along with the assigned topic name, forward it to the Redpanda cluster on central hub.
```
rpk connect run edgepipe.yaml
```

Start the pipeline that consumes from the assigned topic, and only forward the matched hostname to the MQTT broker
```
export ASSIGNED_TOPIC=$(cat ./assigned_topic)
rpk connect run talkpipe.yaml
```

Install the python libraries to start the speech to text application
```
cd s2t/
python3 -m venv env
pip install -r  requirements.txt
```

Start the speech to text application, once start you can enter `s` to start asking question and `e` to stop the listening and start processing your query.
```
source env/bin/activate
python3 stream.py  2>/dev/null
```

Start the application that will trigger your edge device to talk, (input content via MQTT)
```
cd t2s/
python3 talk.py
```


