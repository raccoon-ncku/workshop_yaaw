import pandas as pd
import googlemaps
import os
from dotenv import load_dotenv
from tqdm import tqdm  # for progress bar

def geocode_addresses(input_csv, output_csv):
    # Load environment variables
    load_dotenv()
    
    # Initialize Google Maps client
    gmaps = googlemaps.Client(key=os.getenv('GOOGLE_MAPS_API_KEY'))
    
    # Read the CSV file
    df = pd.read_csv(input_csv)
    
    # Create new columns for latitude and longitude
    df['latitude'] = None
    df['longitude'] = None
    
    # Process each address with progress bar
    for idx in tqdm(range(len(df)), desc="Geocoding addresses"):
        address = df.loc[idx, 'address']
        
        # Skip if address is empty
        if pd.isna(address) or str(address).strip() == '':
            continue
            
        try:
            # Attempt to geocode the address
            geocode_result = gmaps.geocode(address)
            
            # If we got results, extract the coordinates
            if geocode_result and len(geocode_result) > 0:
                location = geocode_result[0]['geometry']['location']
                df.loc[idx, 'latitude'] = location['lat']
                df.loc[idx, 'longitude'] = location['lng']
                
        except Exception as e:
            print(f"Error geocoding address '{address}': {str(e)}")
            continue
    
    # Save the results
    df.to_csv(output_csv, index=False)
    print(f"\nGeocoding complete. Results saved to {output_csv}")
    
    # Print summary statistics
    total_addresses = len(df)
    successful_geocodes = df['latitude'].notna().sum()
    failed_geocodes = total_addresses - successful_geocodes
    
    print(f"\nSummary:")
    print(f"Total addresses processed: {total_addresses}")
    print(f"Successful geocoding: {successful_geocodes}")
    print(f"Failed geocoding: {failed_geocodes}")
    print(f"Success rate: {(successful_geocodes/total_addresses*100):.1f}%")

if __name__ == "__main__":
    # Usage example
    input_file = "addresses.csv"  # Your input CSV file
    output_file = "addresses_with_coords.csv"  # Where to save the results
    
    geocode_addresses(input_file, output_file)