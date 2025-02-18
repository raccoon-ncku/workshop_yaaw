import googlemaps
import os
from dotenv import load_dotenv
import csv
import time
from math import radians, cos, sin, asin, sqrt
from datetime import datetime
import pandas as pd
import signal
import sys
import logging
import json
from googlemaps import exceptions as gmaps_exceptions

# Configuration
load_dotenv()
CENTER_POINT = "台南火車站"
MAX_RADIUS_KM = 1
SEARCH_KEYWORD = "restaurant"
GRID_DENSITY_KM = 0.1
MAX_API_CALLS = 1000
MAX_CALLS_PER_POINT = 3
API_DELAY_SECONDS = 0.05

OUTPUT_FILE = f"places_{SEARCH_KEYWORD}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

POINT_QUERY_RADIUS_KM = MAX_RADIUS_KM / (2 * GRID_DENSITY_KM)

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
    """Save current results to CSV"""
    if found_places:
        # Create interrupted filename if keyboard interrupted
        filename = OUTPUT_FILE
        if interrupted:
            base, ext = os.path.splitext(OUTPUT_FILE)
            filename = f"{base}_interrupted{ext}"
            
        df = pd.DataFrame.from_dict(found_places, orient='index')
        df.to_csv(filename, index=False, encoding='utf-8-sig')
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
        logging.debug(f"Geocode response: {json.dumps(geocode_result, ensure_ascii=False, indent=2)}")
        
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
                    # "radius": int(POINT_QUERY_RADIUS_KM * 1000),
                    "keyword": SEARCH_KEYWORD,
                    "rank_by": "distance",
                    # "page_token": token
                }
                logging.info(f"Making places_nearby request with params: {json.dumps(request_params, ensure_ascii=False)}")
                
                try:
                    places_result = gmaps.places_nearby(**request_params)
                    api_calls += 1
                    point_api_calls += 1
                    
                    logging.debug(f"places_nearby response: {json.dumps(places_result, ensure_ascii=False, indent=2)}")
                    logging.info(f"Results count: {len(places_result.get('results', []))}")

                except gmaps_exceptions.ApiError as e:
                    if "INVALID_REQUEST" in str(e):
                        logging.warning(f"Invalid request for point {point_index}, skipping to next point. Error: {str(e)}")
                        break  # Break the while loop to move to next point
                    else:
                        logging.error(f"API Error: {str(e)}")
                        raise  # Re-raise if it's not an INVALID_REQUEST error

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
                        details = gmaps.place(place_id, fields=[
                            'name', 'formatted_address', 'geometry', 'rating',
                            'user_ratings_total', 'formatted_phone_number',
                            'opening_hours', 'website'
                        ])
                        api_calls += 1
                        # point_api_calls += 1
                        
                        logging.debug(f"Place details response: {json.dumps(details, ensure_ascii=False, indent=2)}")
                        
                        place_details = details['result']
                        found_places[place_id] = {
                            'name': place_details.get('name', ''),
                            'address': place_details.get('formatted_address', ''),
                            'latitude': place_details['geometry']['location']['lat'],
                            'longitude': place_details['geometry']['location']['lng'],
                            'rating': place_details.get('rating', ''),
                            'total_ratings': place_details.get('user_ratings_total', ''),
                            'phone': place_details.get('formatted_phone_number', ''),
                            'website': place_details.get('website', ''),
                            'is_open': place_details.get('opening_hours', {}).get('open_now', '')
                        }
                        new_places += 1
                        logging.debug(f"Successfully added new place: {place_details.get('name', '')}")
                        
                    except gmaps_exceptions.ApiError as e:
                        if "INVALID_REQUEST" in str(e):
                            logging.warning(f"Invalid request for place details {place_id}, skipping. Error: {str(e)}")
                            continue  # Skip to next place
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