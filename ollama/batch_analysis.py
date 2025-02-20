import requests
import base64
import json
import os
import time
import pandas as pd
from tqdm import tqdm

def clean_text_for_csv(text):
    """
    Clean text to make it safe for CSV storage by removing problematic characters
    
    :param text: Text to clean
    :return: Cleaned text
    """
    if text is None:
        return ""
    
    # Replace newlines, carriage returns and tabs with spaces
    text = text.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')
    
    # Replace multiple spaces with single space
    text = ' '.join(text.split())
    
    # Remove any quotes that might interfere with CSV
    text = text.replace('"', "'")
    
    # Strip any leading/trailing whitespace
    return text.strip()

def analyze_image_with_ollama(image_path, model='llava:7b', prompt='Describe this image in detail'):
    """
    Send an image to Ollama server for analysis
    
    :param image_path: Path to the image file
    :param model: Ollama model to use (default: 'llava')
    :param prompt: Analysis prompt
    :return: Analysis response from the Ollama server
    """
    try:
        # Read and encode image
        with open(image_path, 'rb') as image_file:
            image_base64 = base64.b64encode(image_file.read()).decode('utf-8')
    except FileNotFoundError:
        print(f"Warning: Image not found at path: {image_path}")
        return None
    except Exception as e:
        print(f"Error reading image {image_path}: {e}")
        return None
    
    # Prepare request payload
    payload = {
        "model": model,
        "prompt": prompt,
        "images": [image_base64]
    }
    
    # Server URL (adjust as needed)
    url = 'http://192.168.30.1:11434/api/generate'
    
    try:
        # Send POST request
        response = requests.post(url, json=payload, stream=True)
        response.raise_for_status()
        
        # Process streaming response
        full_response = ""
        for line in response.iter_lines():
            if line:
                try:
                    json_response = json.loads(line.decode('utf-8'))
                    if 'response' in json_response:
                        full_response += json_response['response']
                    if json_response.get('done', False):
                        break
                except json.JSONDecodeError:
                    print(f"Error decoding JSON response for {image_path}")
        
        return full_response.strip()
    
    except requests.RequestException as e:
        print(f"Error communicating with Ollama server for {image_path}: {e}")
        return None

def process_images_from_csv(csv_path, prompts, model='llava:7b'):
    """
    Process images listed in a CSV file with multiple prompts
    
    :param csv_path: Path to the CSV file containing image paths
    :param prompts: List of tuples (prompt_title, prompt_content)
    :param model: Ollama model to use
    :return: DataFrame with analysis results
    """
    try:
        # Read CSV file
        df = pd.read_csv(csv_path)
        
        if 'full_path' not in df.columns:
            raise ValueError("CSV must contain 'full_path' column")
        
        # Initialize progress bar
        total_operations = len(df) * len(prompts)
        progress_bar = tqdm(total=total_operations, desc="Processing images")
        
        start_time = time.time()
        
        # Process each prompt
        for prompt_title, prompt_content in prompts:
            results = []
            
            for image_path in df['full_path']:
                analysis = analyze_image_with_ollama(image_path, model, prompt_content)
                # Clean the response text for CSV storage
                cleaned_analysis = clean_text_for_csv(analysis)
                results.append(cleaned_analysis)
                progress_bar.update(1)
            
            # Add results as new column
            df[prompt_title] = results
        
        end_time = time.time()
        progress_bar.close()
        
        # Print statistics
        total_time = end_time - start_time
        images_count = len(df)
        prompts_count = len(prompts)
        
        print("\nProcessing Statistics:")
        print(f"Total time: {total_time:.2f} seconds")
        print(f"Images processed: {images_count}")
        print(f"Prompts per image: {prompts_count}")
        print(f"Average time per image: {total_time/images_count:.2f} seconds")
        print(f"Average time per analysis: {total_time/(images_count*prompts_count):.2f} seconds")
        
        return df
    
    except Exception as e:
        print(f"Error processing CSV: {e}")
        return None

# Example usage
if __name__ == "__main__":
    # Define your prompts as (title, content) tuples
    analysis_prompts = [
        ("summary", "Summarize this image in one sentence"),
        ("objects", "List the main objects in this image, each only one word"),
        ("mood", "Describe the mood or atmosphere of this image in one or two word")
    ]
    
    # Process images
    csv_path = "my_street_view_project/metadata.csv"  # Your CSV file path
    model = "llava:7b"  # Your chosen model
    
    result_df = process_images_from_csv(csv_path, analysis_prompts, model)
    
    if result_df is not None:
        # Save results to new CSV
        output_path = "analysis_results.csv"
        result_df.to_csv(output_path, index=False)
        print(f"\nResults saved to: {output_path}")