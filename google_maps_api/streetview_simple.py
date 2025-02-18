import os
import pathlib
import requests
import time

from dotenv import load_dotenv

load_dotenv()  # take environment variables from .env.

API_KEY = key=os.getenv('GOOGLE_MAPS_API_KEY')
TIMEZONE_BASE_URL = "https://maps.googleapis.com/maps/api/timezone/json"
STREETVIEW_BASE_URL = "https://maps.googleapis.com/maps/api/streetview"
PWD = pathlib.Path(__file__).parent.absolute()

def timezone(lat, lng, timestamp):
    """# Build the parameters dictionary"""
    params = {
        "location": f"{lat},{lng}",
        "timestamp": timestamp,
        "key": API_KEY
    }

    current_delay = 0.1  # Initial retry delay of 100ms
    max_delay = 5  # Maximum retry delay of 5 seconds

    while True:
        try:
            # Make the GET request using requests
            response = requests.get(TIMEZONE_BASE_URL, params=params)
            response.raise_for_status()  # Raises an HTTPError for bad responses
            
            result = response.json()

            if result["status"] == "OK":
                return result["timeZoneId"]
            elif result["status"] != "UNKNOWN_ERROR":
                # Many API errors cannot be fixed by a retry, e.g. INVALID_REQUEST or
                # ZERO_RESULTS. There is no point retrying these requests.
                raise Exception(result["error_message"])

        except (requests.exceptions.RequestException, requests.exceptions.JSONDecodeError):
            if current_delay > max_delay:
                raise Exception("Too many retry attempts.")

            print("Waiting", current_delay, "seconds before retrying.")
            time.sleep(current_delay)
            current_delay *= 2  # Increase the delay each time we retry


def streetview(lat, lng, heading, pitch, fov=90, size_x=640, size_y=640):
    """
    Fetch a Google Street View image for the given location and parameters.
    
    Args:
        lat (float): Latitude
        lng (float): Longitude
        heading (float): Camera heading in degrees (0 to 360)
        pitch (float): Camera pitch in degrees (-90 to 90)
        fov (float, optional): Field of view in degrees. Defaults to 90
        size_x (int, optional): Image width in pixels. Defaults to 640
        size_y (int, optional): Image height in pixels. Defaults to 640
        
    Returns:
        Path: Path to the saved image file
    
    Raises:
        Exception: If the request fails after maximum retries or receives an error response
    """
    params = {
        "size": f"{size_x}x{size_y}",
        "location": f"{lat},{lng}",
        "heading": heading,
        "fov": fov,
        "pitch": pitch,
        "key": API_KEY,
        "return_error_code": "true"
    }

    current_delay = 0.1  # Initial retry delay of 100ms
    max_delay = 5  # Maximum retry delay of 5 seconds

    while True:
        try:
            # Get the API response
            response = requests.get(STREETVIEW_BASE_URL, params=params)
            response.raise_for_status()
            
            # Check if we received an image (Street View API returns image directly)
            if response.headers['content-type'].startswith('image/'):
                # Generate unique filename using all parameters
                # 0 padding the lat/lng to 6 decimal places
                lat_str = f"{lat:.6f}"
                lng_str = f"{lng:.6f}"
                filename = f"{lat_str}_{lng_str}_{heading}_{pitch}_{fov}.jpg"
                filepath = PWD / "streetview" / filename
                # if filename is exist, skip this request
                
                if filepath.exists():
                    return

                # Create the directory if it doesn't exist
                os.makedirs(filepath.parent, exist_ok=True)
                
                # Save the image
                with open(filepath, "wb") as file:
                    file.write(response.content)
                
                return filepath
            else:
                # If we didn't get an image, there might be an error response in JSON
                try:
                    result = response.json()
                    if 'error_message' in result:
                        raise Exception(f"API Error: {result['error_message']}")
                except requests.exceptions.JSONDecodeError:
                    raise Exception("Unexpected response format from API")

        except requests.exceptions.RequestException as e:
            if current_delay > max_delay:
                raise Exception(f"Failed after maximum retries: {str(e)}")

            print(f"Request failed. Waiting {current_delay} seconds before retrying.")
            time.sleep(current_delay)
            current_delay *= 2  # Increase the delay each time we retry

    
if __name__ == "__main__":
    for i in range(0, 360, 30):
        streetview(23.021248, 120.202918, i, 0, 240, 640, 640)
    