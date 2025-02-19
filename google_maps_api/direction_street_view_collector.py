import os
import pathlib
import requests
import time
import csv
from datetime import datetime
from math import radians, sin, cos, sqrt, atan2
import googlemaps
from dotenv import load_dotenv
from tqdm import tqdm

# Load environment variables
load_dotenv()

# Global Configuration
PROJECT_NAME = "my_street_view_project"
STREETVIEW_INTERVAL = 1000  # meters between each street view capture
MAX_API_CALLS = 500  # Maximum number of API calls allowed
STREETVIEW_ANGLES = [0, 90, 180, 270]  # List of angles to capture at each point
STREETVIEW_PARAMS = {
    "fov": 90,
    "pitch": 0,
    "size_x": 640,
    "size_y": 640
}

# API Configuration
GOOGLE_MAPS_API_KEY = os.getenv('GOOGLE_MAPS_API_KEY')
STREETVIEW_BASE_URL = "https://maps.googleapis.com/maps/api/streetview"
gmaps = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)

class APICallCounter:
    def __init__(self, max_calls):
        self.max_calls = max_calls
        self.current_calls = 0
        self.pbar = tqdm(total=max_calls, desc="API Calls", position=0)
    
    def increment(self):
        if self.current_calls >= self.max_calls:
            raise Exception(f"Maximum API calls ({self.max_calls}) reached")
        self.current_calls += 1
        self.pbar.update(1)
        return self.current_calls
    
    def close(self):
        self.pbar.close()

def decode_polyline(polyline_str):
    """Decodes a Google Maps encoded polyline string."""
    index, lat, lng = 0, 0, 0
    coordinates = []
    changes = {'latitude': 0, 'longitude': 0}

    while index < len(polyline_str):
        for unit in ['latitude', 'longitude']:
            shift, result = 0, 0
            while True:
                byte = ord(polyline_str[index]) - 63
                index += 1
                result |= (byte & 0x1f) << shift
                shift += 5
                if not byte >= 0x20:
                    break
            if (result & 1):
                changes[unit] = ~(result >> 1)
            else:
                changes[unit] = (result >> 1)

        lat += changes['latitude']
        lng += changes['longitude']
        coordinates.append((lat / 100000.0, lng / 100000.0))

    return coordinates

def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate the distance between two points on Earth."""
    R = 6371000  # Earth's radius in meters

    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return R * c

def interpolate_points(coordinates, interval):
    """Interpolate points along the path at specified intervals."""
    interpolated = [coordinates[0]]
    accumulated_distance = 0
    
    for i in range(len(coordinates)-1):
        start_lat, start_lng = coordinates[i]
        end_lat, end_lng = coordinates[i+1]
        
        segment_distance = haversine_distance(start_lat, start_lng, end_lat, end_lng)
        accumulated_distance += segment_distance
        
        while accumulated_distance >= interval:
            # Calculate the fraction of the distance to interpolate
            fraction = 1 - (accumulated_distance - interval) / segment_distance
            
            # Linear interpolation
            new_lat = start_lat + (end_lat - start_lat) * fraction
            new_lng = start_lng + (end_lng - start_lng) * fraction
            
            interpolated.append((new_lat, new_lng))
            accumulated_distance -= interval
    
    return interpolated

def fetch_streetview(lat, lng, heading, api_counter, **params):
    """Fetch a Google Street View image with retry logic."""
    image_params = {
        "size": f"{params['size_x']}x{params['size_y']}",
        "location": f"{lat},{lng}",
        "heading": heading,
        "fov": params['fov'],
        "pitch": params['pitch'],
        "key": GOOGLE_MAPS_API_KEY,
        "return_error_code": "true"
    }

    current_delay = 0.1
    max_delay = 5

    while True:
        try:
            api_counter.increment()
            response = requests.get(STREETVIEW_BASE_URL, params=image_params)
            response.raise_for_status()

            if response.headers['content-type'].startswith('image/'):
                lat_str = f"{lat:.6f}"
                lng_str = f"{lng:.6f}"
                filename = f"{lat_str}_{lng_str}_{heading}_{params['pitch']}_{params['fov']}.jpg"
                
                project_dir = pathlib.Path(PROJECT_NAME)
                filepath = project_dir / "images" / filename
                
                if filepath.exists():
                    return filepath

                os.makedirs(filepath.parent, exist_ok=True)
                
                with open(filepath, "wb") as file:
                    file.write(response.content)
                
                return filepath
            else:
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
            current_delay *= 2

def collect_streetview_data(start_location, end_location):
    """Collect Street View images along a route and save metadata to CSV."""
    print(f"\nInitializing Street View collection from {start_location} to {end_location}")
    
    # Initialize API call counter
    api_counter = APICallCounter(MAX_API_CALLS)
    
    try:
        # Get directions
        print("Fetching route directions...")
        directions_result = gmaps.directions(
            start_location,
            end_location,
            mode="driving",
            departure_time=datetime.now()
        )
        
        if not directions_result:
            raise Exception("No route found")
        
        # Calculate total distance
        route_points = decode_polyline(directions_result[0]['overview_polyline']['points'])
        total_distance = sum(
            haversine_distance(route_points[i][0], route_points[i][1], 
                             route_points[i+1][0], route_points[i+1][1])
            for i in range(len(route_points)-1)
        )
        
        print(f"\nRoute Details:")
        print(f"Total distance: {total_distance/1000:.2f} km")
        print(f"Sampling interval: {STREETVIEW_INTERVAL} meters")
        
        # Interpolate points along the route
        print("Calculating sampling points...")
        sampling_points = interpolate_points(route_points, STREETVIEW_INTERVAL)
        estimated_images = len(sampling_points) * len(STREETVIEW_ANGLES)
        
        print(f"Number of sampling points: {len(sampling_points)}")
        print(f"View angles per point: {len(STREETVIEW_ANGLES)}")
        print(f"Total images to collect: {estimated_images}")
        
        if estimated_images > MAX_API_CALLS:
            raise Exception(f"Estimated API calls ({estimated_images}) exceeds maximum limit ({MAX_API_CALLS})")
        
        # Create project directory and CSV file
        project_dir = pathlib.Path(PROJECT_NAME)
        os.makedirs(project_dir / "images", exist_ok=True)
        
        csv_path = project_dir / "metadata.csv"
        csv_fields = ['filename', 'full_path', 'latitude', 'longitude', 'heading', 'pitch', 'fov']
        
        print(f"\nSaving data to {project_dir}")
        
        with open(csv_path, 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=csv_fields)
            writer.writeheader()
            
            # Progress bar for sampling points
            pbar_points = tqdm(sampling_points, desc="Sampling Points", position=1)
            
            # Collect street view images for each point
            for lat, lng in pbar_points:
                for heading in STREETVIEW_ANGLES:
                    try:
                        filepath = fetch_streetview(lat, lng, heading, api_counter, **STREETVIEW_PARAMS)
                        
                        # Write metadata to CSV
                        writer.writerow({
                            'filename': filepath.name,
                            'full_path': str(filepath),
                            'latitude': lat,
                            'longitude': lng,
                            'heading': heading,
                            'pitch': STREETVIEW_PARAMS['pitch'],
                            'fov': STREETVIEW_PARAMS['fov']
                        })
                        
                    except Exception as e:
                        print(f"\nError capturing street view at ({lat}, {lng}, {heading}): {str(e)}")
            
            pbar_points.close()
    
    finally:
        api_counter.close()
    
    # Print summary
    print(f"\nCollection Summary:")
    print(f"Total API calls made: {api_counter.current_calls}")
    print(f"Images collected: {sum(1 for _ in project_dir.glob('images/*.jpg'))}")
    print(f"Output directory: {project_dir.absolute()}")
    print(f"Metadata file: {csv_path.absolute()}")

if __name__ == "__main__":
    # Example usage
    START_LOCATION = "南科管理局"
    END_LOCATION = "台江國家公園"
    
    try:
        collect_streetview_data(START_LOCATION, END_LOCATION)
        print("\nStreet View collection completed successfully!")
    except Exception as e:
        print(f"\nError: {str(e)}")