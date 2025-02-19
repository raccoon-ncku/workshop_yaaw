import googlemaps
import os
from dotenv import load_dotenv
import time
from math import radians, cos, sin, asin, sqrt
from datetime import datetime
import json
import logging
import sys
from googlemaps import exceptions as gmaps_exceptions

# Configuration
load_dotenv()
CENTER_POINT = "台南火車站"
MAX_RADIUS_KM = 1
SEARCH_KEYWORD = "restaurant"
GRID_DENSITY_KM = 0.3
MAX_API_CALLS = 1000
MAX_CALLS_PER_POINT = 3
API_DELAY_SECONDS = 0.05

OUTPUT_FILE = f"places_{SEARCH_KEYWORD}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.geojson"

POINT_QUERY_RADIUS_KM = MAX_RADIUS_KM / (2 * GRID_DENSITY_KM)

# All available fields from Places API
PLACE_FIELDS = [
    'adr_address',
    'business_status',
    'curbside_pickup',
    'current_opening_hours',
    'delivery',
    'dine_in',
    'editorial_summary',
    'formatted_address',
    'formatted_phone_number',
    'geometry',
    'international_phone_number',
    'name',
    'opening_hours',
    'place_id',
    'plus_code',
    'price_level',
    'rating',
    'reservable',
    'reviews',
    'secondary_opening_hours',
    'serves_beer',
    'serves_breakfast',
    'serves_brunch',
    'serves_dinner',
    'serves_lunch',
    'serves_vegetarian_food',
    'serves_wine',
    'takeout',
    'url',
    'user_ratings_total',
    'utc_offset',
    'vicinity',
    'website',
    'wheelchair_accessible_entrance'
]

gmaps = googlemaps.Client(key=os.getenv('GOOGLE_MAPS_API_KEY'))

# Set up logging
log_filename = f"places_search_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_filename, encoding='utf-8'),
        logging.StreamHandler()
    ]
)

def haversine_distance(lat1, lon1, lat2, lon2):
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1 
    dlat = lat2 - lat1 
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a)) 
    r = 6371
    return c * r

def generate_grid_points(center_lat, center_lng, max_radius_km, density_km):
    points = [(center_lat, center_lng)]
    
    lat_degree = density_km / 111
    lng_degree = density_km / (111 * cos(radians(center_lat)))
    
    lat_steps = int(max_radius_km / density_km)
    lng_steps = int(max_radius_km / density_km)
    
    for i in range(-lat_steps, lat_steps + 1):
        for j in range(-lng_steps, lng_steps + 1):
            new_lat = center_lat + (i * lat_degree)
            new_lng = center_lng + (j * lng_degree)
            
            if i == 0 and j == 0:
                continue
                
            if haversine_distance(center_lat, center_lng, new_lat, new_lng) <= max_radius_km:
                points.append((new_lat, new_lng))
    
    return points

def save_results(found_places, interrupted=False):
    """Save current results to GeoJSON"""
    if found_places:
        # Create interrupted filename if keyboard interrupted
        filename = OUTPUT_FILE
        if interrupted:
            base, ext = os.path.splitext(OUTPUT_FILE)
            filename = f"{base}_interrupted{ext}"
        
        # Convert to GeoJSON format
        features = []
        for place_id, place in found_places.items():
            geometry = {
                "type": "Point",
                "coordinates": [place.get('longitude', 0), place.get('latitude', 0)]
            }
            
            # Remove latitude and longitude from properties as they're in geometry
            properties = place.copy()
            properties.pop('latitude', None)
            properties.pop('longitude', None)
            
            feature = {
                "type": "Feature",
                "geometry": geometry,
                "properties": properties,
                "id": place_id
            }
            features.append(feature)
        
        geojson = {
            "type": "FeatureCollection",
            "features": features
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(geojson, f, ensure_ascii=False, indent=2)
        print(f"\nSaved {len(found_places)} places to {filename}")
    else:
        print("\nNo places to save")

def search_places():
    api_calls = 0
    found_places = {}

    try:
        logging.info(f"Search initialized with parameters:")
        logging.info(f"Center Point: {CENTER_POINT}")
        logging.info(f"Maximum Radius: {MAX_RADIUS_KM}km")
        logging.info(f"Grid Density: {GRID_DENSITY_KM}km")
        logging.info(f"Point Query Radius: {POINT_QUERY_RADIUS_KM}km")
        logging.info(f"Search Keyword: {SEARCH_KEYWORD}")

        logging.info("Geocoding center point...")
        geocode_result = gmaps.geocode(CENTER_POINT)
        
        if not geocode_result:
            raise Exception(f"Could not geocode center point: {CENTER_POINT}")
        
        center_lat = geocode_result[0]['geometry']['location']['lat']
        center_lng = geocode_result[0]['geometry']['location']['lng']
        api_calls += 1

        search_points = generate_grid_points(
            center_lat, 
            center_lng, 
            MAX_RADIUS_KM, 
            GRID_DENSITY_KM
        )
        
        total_points = len(search_points)
        logging.info(f"Generated {total_points} search points")

        for point_index, (point_lat, point_lng) in enumerate(search_points, 1):
            if api_calls >= MAX_API_CALLS:
                logging.warning(f"Reached maximum total API calls limit ({MAX_API_CALLS})")
                break

            logging.info(f"\nSearching point {point_index}/{total_points} at {point_lat:.4f}, {point_lng:.4f}")
            
            point_api_calls = 0
            token = None
            
            while True:
                if api_calls >= MAX_API_CALLS or point_api_calls >= MAX_CALLS_PER_POINT:
                    if point_api_calls >= MAX_CALLS_PER_POINT:
                        logging.info(f"Reached maximum API calls for this point ({MAX_CALLS_PER_POINT})")
                    break
                    
                time.sleep(API_DELAY_SECONDS)
                
                request_params = {
                    "location": (point_lat, point_lng),
                    "keyword": SEARCH_KEYWORD,
                    "rank_by": "distance"
                }
                
                try:
                    places_result = gmaps.places_nearby(**request_params)
                    api_calls += 1
                    point_api_calls += 1

                except gmaps_exceptions.ApiError as e:
                    if "INVALID_REQUEST" in str(e):
                        logging.warning(f"Invalid request for point {point_index}, skipping to next point. Error: {str(e)}")
                        break
                    else:
                        logging.error(f"API Error: {str(e)}")
                        raise

                new_places = 0
                for place in places_result.get('results', []):
                    place_id = place['place_id']
                    
                    if place_id in found_places:
                        logging.debug(f"Skipping duplicate place_id: {place_id}")
                        continue
                    
                    if point_api_calls >= MAX_CALLS_PER_POINT:
                        logging.info("Reached API call limit for this point, skipping remaining places")
                        break
                    
                    time.sleep(API_DELAY_SECONDS)
                    try:
                        logging.debug(f"Requesting details for place_id: {place_id}")
                        details = gmaps.place(place_id, fields=PLACE_FIELDS)
                        api_calls += 1
                        
                        place_details = details['result']
                        
                        # Extract coordinates for GeoJSON
                        lat = place_details['geometry']['location']['lat']
                        lng = place_details['geometry']['location']['lng']
                        
                        # Store all available fields
                        found_places[place_id] = {
                            field: place_details.get(field) 
                            for field in PLACE_FIELDS 
                            if field != 'geometry'  # Handle geometry separately for GeoJSON
                        }
                        
                        # Add coordinates for GeoJSON conversion
                        found_places[place_id].update({
                            'latitude': lat,
                            'longitude': lng
                        })
                        
                        new_places += 1
                        logging.debug(f"Successfully added new place: {place_details.get('name', '')}")
                        
                    except gmaps_exceptions.ApiError as e:
                        if "INVALID_REQUEST" in str(e):
                            logging.warning(f"Invalid request for place details {place_id}, skipping. Error: {str(e)}")
                            continue
                        else:
                            logging.error(f"API Error while getting place details: {str(e)}")
                            raise

                    except Exception as e:
                        logging.error(f"Error getting details for place {place_id}: {str(e)}")
                        continue

                logging.info(f"Found {new_places} new places at this point")
                logging.info(f"Total unique places so far: {len(found_places)}")

                token = places_result.get('next_page_token')
                if not token or point_api_calls >= MAX_CALLS_PER_POINT:
                    logging.info("No more pages available or reached point limit")
                    break

            logging.info(f"Completed point {point_index} with {point_api_calls} API calls")

        save_results(found_places)
        logging.info(f"Final API calls made: {api_calls}/{MAX_API_CALLS}")

    except KeyboardInterrupt:
        logging.warning("\nKeyboard interrupt detected!")
        save_results(found_places, interrupted=True)
        logging.info(f"Process interrupted after {api_calls} API calls")
        sys.exit(0)
    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")
        save_results(found_places, interrupted=True)
        raise

if __name__ == "__main__":
    search_places()