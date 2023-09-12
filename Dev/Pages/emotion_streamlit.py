import cv2
import os
import streamlit as st
import streamlit.components.v1 as components
import numpy as np
import requests
from PIL import Image
import tempfile
import threading
import mysql.connector
import uuid 
from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv
import os

HOST_URL = 'http://20.124.81.163:5000/'

load_dotenv()
# Connect to the MySQL database
db_connection = mysql.connector.connect(
    host= 'localhost',
    user=os.getenv("user"),
    password=os.getenv("password"),
    database=os.getenv("database"))

st.sidebar.success("Select page from above")

# Upload the image to Azure Blob Storage
connection_string = "DefaultEndpointsProtocol=https;AccountName=signalstoragecontent;AccountKey=W2KtrfbEYkgE35Ei4TMRFGf8/BhODwSzjxAAamAly9SgLShyUayRKbt/D6v9tRiR+qK2dPOAhNFz+ASttDGWuQ==;EndpointSuffix=core.windows.net"
blob_service_client = BlobServiceClient.from_connection_string(connection_string)

col1, col2 = st.columns(2)
with col1:
    def save_image_and_emotion(frame_image, emotion):
        # Generate a unique filename using UUID
        unique_filename = str(emotion) + '_' + str(uuid.uuid4()) + '.jpg'
        
        os.makedirs('face_emotion', exist_ok=True)
        # Save the frame as an image
        image_path = os.path.join('face_emotion', unique_filename)
        cv2.imwrite(image_path, frame_image)
        
        blob_client = blob_service_client.get_blob_client(container="signaltest", blob=image_path)
        
        with open(image_path, "rb") as data:
            blob_client.upload_blob(data)

        os.remove(image_path)

        # Insert the information into the database
        try:
            with db_connection.cursor() as cursor:
                sql = "INSERT INTO face_emotion (image_path, emotion) VALUES (%s, %s)"
                cursor.execute(sql, (image_path, emotion))
            db_connection.commit()
        except Exception as e:
            db_connection.rollback()
            raise Exception("Error inserting data into the database: " + str(e))

    # Global variable to store the results
    global_result = "Starting..."

    # Function to predict emotion using an external service asynchronously
    def emotion_predict_async(frame_image):
        global global_result
        
        # Create a temporary file to store the frame image
        temp_file = tempfile.NamedTemporaryFile(delete=False)
        temp_filename = temp_file.name + '.jpg'
        cv2.imwrite(temp_filename, frame_image)
        
        url = HOST_URL + 'emotion-detector'

        try:
            with open(temp_filename, 'rb') as image_file:
                files = {'img': image_file}
                response = requests.post(url=url, files=files)
                if response.status_code == 200:
                    result = response.json()  
                    emotion = result["emotion"]
                    global_result = emotion 
                    t1 = threading.Thread(target=save_image_and_emotion, args=(frame_image, emotion))
                    t1.start()

        except requests.exceptions.RequestException as e:
            raise Exception("An error occurred: " + str(e))
        finally:
            os.unlink(temp_filename)  # Remove the temporary file


    cap = cv2.VideoCapture(0)
    st.title("Video Stream")

    frame_placeholder = st.empty()

    def callback():
        st.session_state['is_running'] = True

    start_button = st.button('Start', on_click=callback)

    frame_count = 0
    frame_processing = 90

    # Font
    font = cv2.FONT_HERSHEY_SIMPLEX
    # Org
    org = (50, 50)
    # FontScale
    fontScale = 1
    # Blue color in BGR
    color = (255, 0, 0)
    # Line thickness of 2 px
    thickness = 2

    if start_button:
        if st.button('Stop'):
            st.session_state['is_running'] = False
        else:
            while st.session_state['is_running']:
                ret, frame = cap.read()
                frame_count += 1
                image = frame.copy()
                if frame_count % frame_processing == 0:
                    t1 = threading.Thread(target=emotion_predict_async, args=(image,))
                    t1.start()

                if global_result:
                    # Get the latest prediction
                    frame_with_text = cv2.putText(frame, global_result, org, font, fontScale, color, thickness, cv2.LINE_AA)
                    frame_placeholder.image(cv2.cvtColor(frame_with_text, cv2.COLOR_BGR2RGB), channels="RGB")
                else:
                    frame_placeholder.image(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB), channels="RGB")

    db_connection.close()
    cap.release()
    cv2.destroyAllWindows()

with col2:
    st.write("Video")
    components.html(
    """
    <!DOCTYPE html>
    <html>
    <body>
        <!-- 1. The <iframe> (and video player) will replace this <div> tag. -->
        <div id="player"></div>
        <p>Time: <span id="time">0</span> seconds</p>
        <script>
    // Load the IFrame Player API code asynchronously.
    var tag = document.createElement("script");

    tag.src = "https://www.youtube.com/iframe_api";
    var firstScriptTag = document.getElementsByTagName("script")[0];
    firstScriptTag.parentNode.insertBefore(tag, firstScriptTag);

    // Instantiate the Player.
    function onYouTubeIframeAPIReady() {
    var player = new YT.Player("player", {
        height: "390",
        width: "640",
        videoId: "M7lc1UVf-VE"
    });

    // This is the source "window" that will emit the events.
    var iframeWindow = player.getIframe().contentWindow;

    // So we can compare against new updates.
    var lastTimeUpdate = 0;

    // Listen to events triggered by postMessage,
    // this is how different windows in a browser
    // (such as a popup or iFrame) can communicate.
    // See: https://developer.mozilla.org/en-US/docs/Web/API/Window/postMessage
    window.addEventListener("message", function(event) {
        // Check that the event was sent from the YouTube IFrame.
        if (event.source === iframeWindow) {
        var data = JSON.parse(event.data);

        // The "infoDelivery" event is used by YT to transmit any
        // kind of information change in the player,
        // such as the current time or a playback quality change.
        if (
            data.event === "infoDelivery" &&
            data.info &&
            data.info.currentTime
        ) {
            // currentTime is emitted very frequently (milliseconds),
            // but we only care about whole second changes.
            var time = Math.floor(data.info.currentTime);

            if (time !== lastTimeUpdate) {
            lastTimeUpdate = time;
            
            // It's now up to you to format the time.
            document.getElementById("time").innerHTML = time;
            }
        }
        }
    });
    }

        </script>
    </body>
    </html>


        """, height = 600
    )
