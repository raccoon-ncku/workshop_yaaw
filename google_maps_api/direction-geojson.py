import googlemaps
import os
from dotenv import load_dotenv
from datetime import datetime
import json
import pytz

# Configuration
load_dotenv()
PROJECT_TITLE = "commute_routes"
LOCATIONS = [
    ("南科管理局", "台江國家公園"),
    ("台南火車站", "安平古堡"),
    ("奇美博物館", "台南美術館")
    # Add more pairs as needed
]

gmaps = googlemaps.Client(key=os.getenv('GOOGLE_MAPS_API_KEY'))

def decode_polyline(polyline_str):
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

        coordinates.append([lng / 100000.0, lat / 100000.0])

    return coordinates

def create_routes_geojson(location_pairs, mode="driving", timezone="Asia/Taipei"):
    # Get current time in specified timezone
    tz = pytz.timezone(timezone)
    current_time = datetime.now(tz)
    
    # Initialize features list for successful routes
    features = []
    
    for start_location, end_location in location_pairs:
        try:
            # Get directions
            directions_result = gmaps.directions(
                start_location,
                end_location,
                mode=mode,
                departure_time=current_time,
            )
            
            if not directions_result:
                print(f"No route found for {start_location} to {end_location}. Skipping...")
                continue
                
            # Create GeoJSON feature for successful route
            route_feature = {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": decode_polyline(directions_result[0]['overview_polyline']['points'])
                },
                "properties": {
                    "start_location": start_location,
                    "end_location": end_location,
                    "travel_mode": mode,
                    "departure_time": current_time.isoformat(),
                    "query_time": current_time.isoformat(),
                    "distance": directions_result[0]['legs'][0]['distance']['text'],
                    "duration": directions_result[0]['legs'][0]['duration']['text'],
                    "duration_in_traffic": directions_result[0]['legs'][0].get('duration_in_traffic', {}).get('text', 'N/A')
                }
            }
            
            features.append(route_feature)
            print(f"Successfully processed route: {start_location} to {end_location}")
            
        except Exception as e:
            print(f"Error processing route from {start_location} to {end_location}: {str(e)}")
            continue
    
    # Only create and save GeoJSON if there are successful routes
    if features:
        # Create GeoJSON FeatureCollection
        geojson_data = {
            "type": "FeatureCollection",
            "features": features,
            "properties": {
                "project": PROJECT_TITLE,
                "created_at": current_time.isoformat(),
                "total_routes": len(features)
            }
        }
        
        # Save to file
        filename = f"{PROJECT_TITLE}_{current_time.strftime('%Y%m%d_%H%M%S')}.geojson"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(geojson_data, f, ensure_ascii=False, indent=2)
        
        print(f"\nSuccessfully saved {len(features)} routes to: {filename}")
        return filename
    else:
        print("\nNo successful routes to save.")
        return None

if __name__ == "__main__":
    output_file = create_routes_geojson(
        LOCATIONS,
        mode="driving"
    )
    
    if output_file:
        print(f"Process completed. File saved as: {output_file}")
    else:
        print("Process completed. No file was saved due to no successful routes.")