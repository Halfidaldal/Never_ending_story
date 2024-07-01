import asyncio
import base64
import websockets
import websocket  # websocket-client library
import uuid
import json
import urllib.request
import urllib.parse
from PIL import Image
import io
import os
import firebase_admin
from firebase_admin import credentials, firestore, storage

# Initialize Firebase Admin SDK
cred = credentials.Certificate("the-never-ending-story-a7b5f-firebase-adminsdk-ax73p-2af6a82ea1.json")  # Replace with the path to your Firebase service account key
firebase_admin.initialize_app(cred, {
    'storageBucket': 'the-never-ending-story-a7b5f.appspot.com'
})
db = firestore.client()
bucket = storage.bucket()

server_address = "130.225.164.141:8188"
client_id = str(uuid.uuid4())

def read_system_id_from_file(filename):
    try:
        with open(filename, 'r') as file:
            content = file.read()
        return content
    except FileNotFoundError:
        return "File not found."
hostname = read_system_id_from_file("system_id.txt")

print(hostname)

def queue_prompt(prompt):
    p = {"prompt": prompt, "client_id": client_id}
    data = json.dumps(p).encode('utf-8')
    req = urllib.request.Request(f"http://{server_address}/prompt", data=data)
    return json.loads(urllib.request.urlopen(req).read())

def get_image(filename, subfolder, folder_type):
    data = {"filename": filename, "subfolder": subfolder, "type": folder_type}
    url_values = urllib.parse.urlencode(data)
    with urllib.request.urlopen(f"http://{server_address}/view?{url_values}") as response:
        return response.read()

def get_history(prompt_id):
    with urllib.request.urlopen(f"http://{server_address}/history/{prompt_id}") as response:
        return json.loads(response.read())



def get_images(prompt_comfy):
    ws = websocket.WebSocket()
    ws.connect(f"ws://{server_address}/ws?clientId={client_id}")
    prompt_id = queue_prompt(prompt_comfy)['prompt_id']
    output_images = {}
    
    while True:
        out = ws.recv()
        if isinstance(out, str):
            message = json.loads(out)
            if message['type'] == 'executing':
                data = message['data']
                if data['node'] is None and data['prompt_id'] == prompt_id:
                    break  # Execution is done
        else:
            continue  # Previews are binary data

    history = get_history(prompt_id)[prompt_id]
    for node_id in history['outputs']:
        node_output = history['outputs'][node_id]
        if 'images' in node_output:
            images_output = []
            for image in node_output['images']:
                image_data = get_image(image['filename'], image['subfolder'], image['type'])
                images_output.append(image_data)
            output_images[node_id] = images_output
    
    ws.close()
    
    return output_images
#sends ping to client
async def message_loop(websocket):
    while True:
        try:
            await websocket.send("ping")
            print("Ping sent to client")
            await asyncio.sleep(10)  # Wait 5 seconds before sending the next ping
        except websockets.exceptions.ConnectionClosed:
            print("Client disconnected, stopping ping loop")
            break

async def server(websocket): #path is not used
    print("A client just connected")
    message_task = asyncio.create_task(message_loop(websocket))
    try:
        async for message in websocket:
            print(f"Received message from client: {message}")
            try:
                # Parse the incoming message as JSON
                with open("pixart_test2.json", "r", encoding="utf-8") as f:
                    workflow_data = f.read()
                prompt_comfy = json.loads(workflow_data)
                prompt_data = json.loads(message)  # Here, prompt_data will be a dictionary
                
                user_part = prompt_data.get('user')
                ai_part = prompt_data.get('ai')
                if user_part is not None and ai_part is not None:
                    combined_prompt = f"{user_part} {ai_part}"
                    prompt_comfy["113"]["inputs"]["text"] = combined_prompt  # Use combined user and AI parts

                    # Process images
                    images = get_images(prompt_comfy)
                    image_urls = []
                    
                    for node_id in images:
                        for image_data in images[node_id]:
                            image = Image.open(io.BytesIO(image_data))
                            image.show()
                            # Save image to Firebase Storage
                            image_byte_array = io.BytesIO()
                            image.save(image_byte_array, format='PNG')
                            image_byte_array.seek(0)
                            blob = bucket.blob(f'images/{node_id}_{user_part[:10]}_{ai_part[:10]}.png')
                            blob.upload_from_file(image_byte_array, content_type='image/png')
                            image_url = blob.public_url
                            image_urls.append(image_url)
                    # Save to Firestore in a single document (is this used?)
                            doc_ref = db.collection("story_data").add({
                            "user": user_part,
                            "ai": ai_part,
                            "combined_prompt": combined_prompt,
                            "image_urls": image_urls,
                            "timestamp": firestore.SERVER_TIMESTAMP,
                            "client_id": hostname,
                            })
                            await websocket.send(json.dumps({"image_urls": image_urls}))
                else:
                    missing_keys = []
                    if user_part is None:
                        missing_keys.append('user')
                    if ai_part is None:
                        missing_keys.append('ai')
                    raise ValueError(f"Missing keys in received data: {', '.join(missing_keys)}")
            except (json.JSONDecodeError, ValueError) as e:
                print(f"Error processing message: {str(e)}")
                continue  # Skip to the next message if the current one is invalid
            
            response = "999"
            await websocket.send(response)
            print(f"Sent response to client: {response}")
    except websockets.exceptions.ConnectionClosed:
        print("A client just disconnected")
    finally:
        message_task.cancel()

async def main():
    print("Server is starting...")
    async with websockets.serve(server, "localhost", 8765):
        await asyncio.Future()  # This will run forever

if __name__ == "__main__":
    asyncio.run(main())