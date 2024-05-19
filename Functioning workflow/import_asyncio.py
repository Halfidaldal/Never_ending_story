import asyncio
import websockets
import websocket  # websocket-client library
import uuid
import json
import urllib.request
import urllib.parse
from PIL import Image
import io

server_address = "127.0.0.1:8188"
client_id = str(uuid.uuid4())

def queue_prompt(prompt):
    p = {"prompt": prompt, "client_id": client_id}
    data = json.dumps(p).encode('utf-8')
    req =  urllib.request.Request(f"http://{server_address}/prompt", data=data)
    return json.loads(urllib.request.urlopen(req).read())

def get_image(filename, subfolder, folder_type):
    data = {"filename": filename, "subfolder": subfolder, "type": folder_type}
    url_values = urllib.parse.urlencode(data)
    with urllib.request.urlopen(f"http://{server_address}/view?{url_values}") as response:
        return response.read()

def get_history(prompt_id):
    with urllib.request.urlopen(f"http://{server_address}/history/{prompt_id}") as response:
        return json.loads(response.read())

def get_images(prompt):
    ws = websocket.WebSocket()
    ws.connect(f"ws://{server_address}/ws?clientId={client_id}")
    prompt_id = queue_prompt(prompt)['prompt_id']
    output_images = {}
    
    while True:
        out = ws.recv()
        if isinstance(out, str):
            message = json.loads(out)
            if message['type'] == 'executing':
                data = message['data']
                if data['node'] is None and data['prompt_id'] == prompt_id:
                    break # Execution is done
        else:
            continue # Previews are binary data

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

async def server(websocket, path):
    print("A client just connected")
    try:
        async for message in websocket:
            print(f"Received message from client: {message}")
            try:
                # Parse the incoming message as JSON
                with open("pixart_test2.json", "r", encoding="utf-8") as f:
                    workflow_data = f.read()
                prompt_comfy = json.loads(workflow_data)
                prompt_data = json.loads(message)  # Here, prompt_data will be a dictionary
                if 'prompt' in prompt_data:
                    prompt_comfy["113"]["inputs"]["text"] = prompt_data['prompt']  # Extract the string associated with the key 'prompt'
                else:
                    raise ValueError("Missing 'prompt' key in received data")
            except (json.JSONDecodeError, ValueError) as e:
                print(f"Error processing message: {str(e)}")
                continue  # Skip to the next message if the current one is invalid

            # Now pass the parsed prompt text to the get_images function
            
            images = get_images(prompt_comfy)
            
            for node_id in images:
                for image_data in images[node_id]:
                    image = Image.open(io.BytesIO(image_data))
                    image.show()  # This shows the image on the server, typically you would send back a response instead
            response = "Images processed and displayed"
            await websocket.send(response)
            print(f"Sent response to client: {response}")
    except websockets.exceptions.ConnectionClosed:
        print("A client just disconnected")


async def main():
    print("Server is starting...")
    async with websockets.serve(server, "localhost", 8765):
        await asyncio.Future()  # This will run forever

if __name__ == "__main__":
    asyncio.run(main())