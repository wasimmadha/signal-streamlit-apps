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

# Global variable to store the results
global_result = None
ref_image_id = None

# Upload the image to Azure Blob Storage
connection_string = "DefaultEndpointsProtocol=https;AccountName=signalstoragecontent;AccountKey=W2KtrfbEYkgE35Ei4TMRFGf8/BhODwSzjxAAamAly9SgLShyUayRKbt/D6v9tRiR+qK2dPOAhNFz+ASttDGWuQ==;EndpointSuffix=core.windows.net"
blob_service_client = BlobServiceClient.from_connection_string(connection_string)

def save_image_and_age(frame_image, verify):
    # Generate a unique filename using UUID
    unique_filename = str(verify) + '_' + str(uuid.uuid4()) + '.jpg'
    
    os.makedirs('face_verify_input', exist_ok=True)

    # Save the frame as an image
    image_path = os.path.join('face_verify_input', unique_filename)
    cv2.imwrite(image_path, frame_image)
    
    blob_client = blob_service_client.get_blob_client(container="signaltest", blob=image_path)
    
    with open(image_path, "rb") as data:
        blob_client.upload_blob(data)

    os.remove(image_path)

    # Insert the information into the database
    try:
        with db_connection.cursor() as cursor:
            sql = "INSERT INTO face_verify (ref_image_id, image_path, verify) VALUES (%s, %s, %s)"
            cursor.execute(sql, (ref_image_id, image_path, verify))
        db_connection.commit()
    except Exception as e:
        db_connection.rollback()
        raise Exception("Error inserting data into the database: " + str(e))

# Function to predict age using an external service asynchronously
def verify_face(frame, ref_image):
    global global_result
    
    # Create a temporary file to store the frame image
    temp_file = tempfile.NamedTemporaryFile(delete=False)
    temp_filename = temp_file.name + '.jpg'
    cv2.imwrite(temp_filename, frame)
    
    url = HOST_URL + 'verify-faces'

    try:
        # Create a dictionary to store the image data
        files = {
            'reference_image': ('reference_image.jpg', open(ref_image, 'rb')),
            'new_image': ('new_image.jpg', open(temp_filename, 'rb'))
        }

        response = requests.post(url=url, files=files)
        if response.status_code == 200:
            result = response.json()  
            face_verified = result['face_verified']
            verification_result = "Verified." if face_verified == 1 else "NotVerified."
            global_result = verification_result

            t1 = threading.Thread(target=save_image_and_age, args=(frame, face_verified))
            t1.start()

    except requests.exceptions.RequestException as e:
        raise Exception("An error occurred: " + str(e))

cap = cv2.VideoCapture(0)
st.title("Video Stream")

# Function to save an uploaded image to a temporary directory and return the file path
def save_uploaded_image(uploaded_image):
    global ref_image_id

    # Create a temporary directory to store the uploaded image
    temp_dir = tempfile.mkdtemp()

    if uploaded_image:
        # Get the file name and extension
        file_name = uploaded_image.name
        file_extension = file_name.split(".")[-1]

        # Create a unique file path in the temporary directory
        temp_file_path = os.path.join(temp_dir, f"uploaded_image.{file_extension}")

        ref_image_id = str(uuid.uuid4())

        # Save the frame as an image
        image_path = os.path.join('reference', f"reference_{ref_image_id}.{file_extension}")
        
        # Save the uploaded image to the temporary directory
        with open(temp_file_path, "wb") as f:
            f.write(uploaded_image.read())

        # Save the uploaded image to blob storage
        image_path = os.path.join('reference', f"reference_{ref_image_id}.{file_extension}")
        blob_client = blob_service_client.get_blob_client(container="signaltest", blob=image_path)
        
        with open(temp_file_path, "rb") as data:
            blob_client.upload_blob(data)

        return temp_file_path

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

uploaded_image = st.file_uploader("Upload an image", type=["jpg", "png", "jpeg"])
temp_file_path = None

if uploaded_image:
    temp_file_path = save_uploaded_image(uploaded_image)
    st.success(f"Image has been saved to: {temp_file_path}")
    st.image(temp_file_path, caption=f"Uploaded Image: {uploaded_image.name}")

if ref_image_id:
    if start_button:
        if st.button('Stop'):
            st.session_state['is_running'] = False
        else:
            try:
                while st.session_state['is_running']:
                    ret, frame = cap.read()
                    if global_result:
                        # Get the latest verification result
                        frame_with_text = cv2.putText(frame, global_result, org, font, fontScale, color, thickness, cv2.LINE_AA)
                        frame_placeholder.image(cv2.cvtColor(frame_with_text, cv2.COLOR_BGR2RGB), channels="RGB")
                    else:
                        frame_placeholder.image(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB), channels="RGB")

                    frame_count += 1
                    if frame_count % frame_processing == 0 and temp_file_path is not None:
                        t1 = threading.Thread(target=verify_face, args=(frame, temp_file_path))
                        t1.start()

            except KeyError:
                st.write('Capturing Stopped')

db_connection.close()
cap.release()
cv2.destroyAllWindows()
