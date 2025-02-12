import requests
import base64
import json
import os
import time

IMAGE_DIR = "./images"
PROMPT = "summarize this image in one sentence"
MODEL = "llava:7b"
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif'}


def analyze_image_with_ollama(image_path, model='llava:7b', prompt='Describe this image in detail'):
    """
    Send an image to Ollama server for analysis
    
    :param image_path: Path to the image file
    :param model: Ollama model to use (default: 'llava')
    :param prompt: Analysis prompt (default: general description)
    :return: Analysis response from the Ollama server
    """
    # Read the image file and encode it to base64
    with open(image_path, 'rb') as image_file:
        image_base64 = base64.b64encode(image_file.read()).decode('utf-8')
    
    # Prepare the request payload
    payload = {
        "model": model,
        "prompt": prompt,
        "images": [image_base64]
    }
    
    # Server URL (adjust to match your Ollama docker setup)
    url = 'http://127.0.0.1:11434/api/generate'
    
    try:
        # Send POST request to Ollama server
        response = requests.post(url, json=payload, stream=True)
        
        # Check if the request was successful
        response.raise_for_status()
        
        # Process the streaming response
        full_response = ""
        for line in response.iter_lines():
            if line:
                try:
                    # Parse each JSON line
                    json_response = json.loads(line.decode('utf-8'))
                    
                    # Check if the response contains a text fragment
                    if 'response' in json_response:
                        full_response += json_response['response']
                    
                    # Check if the stream is complete
                    if json_response.get('done', False):
                        break
                
                except json.JSONDecodeError:
                    print("Error decoding JSON response")
        
        return full_response.strip()
    
    except requests.RequestException as e:
        print(f"Error communicating with Ollama server: {e}")
        return None


start_time = time.time()

for image in os.listdir(IMAGE_DIR):
    if os.path.splitext(image)[1].lower() in IMAGE_EXTENSIONS:
        image_path = os.path.join(IMAGE_DIR, image)
        analysis = analyze_image_with_ollama(image_path, MODEL, PROMPT)
        if analysis:
            print(f"{image}: {analysis}")

end_time = time.time()
print(f"Time taken: {end_time - start_time:.2f} seconds")
print(f"average time taken: {(end_time - start_time)/len(os.listdir(IMAGE_DIR)):.2f} seconds")