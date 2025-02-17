import googlemaps
import os
from dotenv import load_dotenv

load_dotenv()  # take environment variables from .env.
gmaps = googlemaps.Client(key=os.getenv('GOOGLE_MAPS_API_KEY'))

# Geocoding an address
geocode_result = gmaps.geocode('南科管理')
print(geocode_result)

# Display only the latitude and longitude
print(geocode_result[0]['geometry']['location'])