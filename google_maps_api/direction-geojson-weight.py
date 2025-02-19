import googlemaps
import os
from dotenv import load_dotenv
from datetime import datetime
import json
import pytz
import pandas as pd
from collections import defaultdict

# Configuration
load_dotenv()
PROJECT_TITLE = "weighted_routes"

def decode_polyline(polyline_str):
    # Keeping the original decode_polyline function unchanged
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

def segment_key(coord1, coord2):
    """Create a unique key for a segment based on its coordinates"""
    return tuple(sorted([tuple(coord1), tuple(coord2)]))

def create_weighted_routes_geojson(csv_file, mode="driving", timezone="Asia/Taipei"):
    # Read routes from CSV
    routes_df = pd.read_csv(csv_file)
    
    # Initialize Google Maps client
    gmaps = googlemaps.Client(key=os.getenv('GOOGLE_MAPS_API_KEY'))
    
    # Get current time in specified timezone
    tz = pytz.timezone(timezone)
    current_time = datetime.now(tz)
    
    # Dictionary to store segment weights
    segment_weights = defaultdict(float)
    # Dictionary to store segment metadata
    segment_metadata = {}
    
    # Process each route
    for _, row in routes_df.iterrows():
        try:
            directions_result = gmaps.directions(
                row['start'],
                row['destination'],
                mode=mode,
                departure_time=current_time,
            )
            
            if not directions_result:
                print(f"No route found for {row['start']} to {row['destination']}. Skipping...")
                continue
            
            # Decode the polyline to get coordinates
            coords = decode_polyline(directions_result[0]['overview_polyline']['points'])
            
            # Process segments
            for i in range(len(coords) - 1):
                seg_key = segment_key(coords[i], coords[i+1])
                # Add weight to segment
                segment_weights[seg_key] += float(row['weight'])
                
                # Store segment metadata if not already stored
                if seg_key not in segment_metadata:
                    segment_metadata[seg_key] = {
                        'coordinates': [coords[i], coords[i+1]],
                        'start_point': coords[i],
                        'end_point': coords[i+1]
                    }
            
            print(f"Successfully processed route: {row['start']} to {row['destination']}")
            
        except Exception as e:
            print(f"Error processing route from {row['start']} to {row['destination']}: {str(e)}")
            continue
    
    # Combine adjacent segments with same weight
    combined_segments = []
    processed_segments = set()
    
    for seg_key, weight in segment_weights.items():
        if seg_key in processed_segments:
            continue
            
        current_segment = list(segment_metadata[seg_key]['coordinates'])
        current_weight = weight
        processed_segments.add(seg_key)
        
        # Try to extend segment
        while True:
            # Look for adjacent segment with same weight
            extended = False
            for other_seg_key, other_weight in segment_weights.items():
                if other_seg_key in processed_segments:
                    continue
                    
                if abs(other_weight - current_weight) < 0.001:  # Compare with small tolerance
                    other_coords = segment_metadata[other_seg_key]['coordinates']
                    
                    # Check if segments are adjacent
                    if tuple(current_segment[-1]) == tuple(other_coords[0]):
                        current_segment.append(other_coords[1])
                        processed_segments.add(other_seg_key)
                        extended = True
                        break
                    elif tuple(current_segment[0]) == tuple(other_coords[1]):
                        current_segment.insert(0, other_coords[0])
                        processed_segments.add(other_seg_key)
                        extended = True
                        break
            
            if not extended:
                break
        
        # Add combined segment to results
        combined_segments.append({
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": current_segment
            },
            "properties": {
                "weight": current_weight,
                "segment_count": len(current_segment) - 1
            }
        })
    
    # Create final GeoJSON
    geojson_data = {
        "type": "FeatureCollection",
        "features": combined_segments,
        "properties": {
            "project": PROJECT_TITLE,
            "created_at": current_time.isoformat(),
            "total_segments": len(combined_segments)
        }
    }
    
    # Save to file
    filename = f"{PROJECT_TITLE}_{current_time.strftime('%Y%m%d_%H%M%S')}.geojson"
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(geojson_data, f, ensure_ascii=False, indent=2)
    
    print(f"\nSuccessfully saved {len(combined_segments)} weighted segments to: {filename}")
    return filename

if __name__ == "__main__":
    output_file = create_weighted_routes_geojson(
        "routes.csv",  # Your CSV file path
        mode="driving"
    )
    
    if output_file:
        print(f"Process completed. File saved as: {output_file}")
    else:
        print("Process completed. No file was saved due to no successful routes.")