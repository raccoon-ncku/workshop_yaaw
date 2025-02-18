import googlemaps
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()
gmaps = googlemaps.Client(key=os.getenv('GOOGLE_MAPS_API_KEY'))

def decode_polyline(polyline_str ):
    '''
    Decodes a polyline that has been encoded using Google's algorithm

    See http://code.google.com/apis/maps/documentation/polylinealgorithm.html

    This is a generic method that returns a list of (latitude, longitude)
    tuples.


    :param polyline_str: Encoded polyline string.
    :type polyline_str: string
    :returns: List of 2-tuples where each tuple is (latitude, longitude)
    :rtype: list
    '''
    index, lat, lng = 0, 0, 0
    coordinates = []
    changes = {'latitude': 0, 'longitude': 0}

    # Coordinates have variable length when encoded, so just keep
    # track of whether we've hit the end of the string. In each
    # while loop iteration, a single coordinate is decoded.
    while index < len(polyline_str):
        # Gather lat/lon changes, store them in a dictionary to apply them later
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

directions_result = gmaps.directions(
    "南科管理局",
    "台江國家公園",
    mode="driving",
    departure_time=datetime.now(),
)

print(directions_result)
print(decode_polyline(directions_result[0]['overview_polyline']['points']))
