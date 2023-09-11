import cv2
import os
import streamlit as st
import requests
import tempfile
import threading
import mysql.connector
import uuid
from azure.storage.blob import BlobServiceClient

HOST_URL = '20.124.81.163:5000/'

# Connect to the MySQL database
db_connection = mysql.connector.connect(
    host= 'localhost',
    user='root',
    password='password',
    database='staging_dbRD')

# Upload the image to Azure Blob Storage
connection_string = "DefaultEndpointsProtocol=https;AccountName=signalstoragecontent;AccountKey=W2KtrfbEYkgE35Ei4TMRFGf8/BhODwSzjxAAamAly9SgLShyUayRKbt/D6v9tRiR+qK2dPOAhNFz+ASttDGWuQ==;EndpointSuffix=core.windows.net"
blob_service_client = BlobServiceClient.from_connection_string(connection_string)

global_result = ''

def save_image_and_age(frame_image, age):
    # Generate a unique filename using UUID
    unique_filename = str(age) + '_' + str(uuid.uuid4()) + '.jpg'
    
    os.makedirs('face_age', exist_ok=True)

    # Save the frame as an image
    image_path = os.path.join('face_age', unique_filename)
    cv2.imwrite(image_path, frame_image)
    
    blob_client = blob_service_client.get_blob_client(container="signaltest", blob=image_path)
    
    with open(image_path, "rb") as data:
        blob_client.upload_blob(data)

    os.remove(image_path)
    # Insert the information into the database
    try:
        with db_connection.cursor() as cursor:
            sql = "INSERT INTO face_age (image_path, age) VALUES (%s, %s)"
            cursor.execute(sql, (image_path, age))
        db_connection.commit()
    except Exception as e:
        db_connection.rollback()
        raise Exception("Error inserting data into the database: " + str(e))


# Function to predict age using an external service asynchronously
def predict_age_async(frame):
    global global_result
    
    # Create a temporary file to store the frame image
    temp_file = tempfile.NamedTemporaryFile(delete=False)
    temp_filename = temp_file.name + '.jpg'
    cv2.imwrite(temp_filename, frame)
    
    url = HOST_URL + 'predict-age'

    try:
        with open(temp_filename, 'rb') as image_file:
            files = [('file', image_file)]
            response = requests.post(url=url, files=files)
            if response.status_code == 200:
                result = response.json()  
                if result['is_child'] == True:
                    prediction = "Child."
                else:
                    prediction = "Adult."
                
                global_result = prediction 
                t1 = threading.Thread(target=save_image_and_age, args=(frame, prediction))
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
        try:
            while st.session_state['is_running']:
                ret, frame = cap.read()
                frame_count += 1
                if frame_count % frame_processing == 0:
                    t1 = threading.Thread(target=predict_age_async, args=(frame,))
                    t1.start()

                if global_result:
                    frame_with_text = cv2.putText(frame, global_result, org, font, fontScale, color, thickness, cv2.LINE_AA)
                    frame_placeholder.image(cv2.cvtColor(frame_with_text, cv2.COLOR_BGR2RGB), channels="RGB")
                else:
                    frame_placeholder.image(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB), channels="RGB")

        except KeyError:
            st.write('Capturing Stopped')

db_connection.close()
cap.release()
cv2.destroyAllWindows()
