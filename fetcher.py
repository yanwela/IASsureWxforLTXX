# made by alp-1863530
import json
import time
from datetime import datetime, timezone
import requests
from shapely.geometry import shape, Point

def generate_our_fir_grid(grid_interval=1.5):
    """
    Fetches the live VATSpy GeoJSON boundary data from GitHub, filters it for
    LTBB and LTAA FIRs, and generates an optimized coordinate grid inside our airspace.
    """
    geojson_url = "https://raw.githubusercontent.com/vatsimnetwork/vatspy-data-project/master/Boundaries.geojson"
    
    print("[INFO] Fetching live VATSpy GeoJSON boundary data from GitHub...")
    try:
        response = requests.get(geojson_url, timeout=30)
        if response.status_code != 200:
            print(f"[ERROR] Failed to download GeoJSON! HTTP Status: {response.status_code}")
            return []
        geojson_data = response.json()
    except Exception as e:
        print(f"[ERROR] Network connection failed: {e}")
        return []
    
    fir_polygons = []
    for feature in geojson_data['features']:
        fir_id = feature['properties'].get('id', '')
        if fir_id in ['LTBB', 'LTAA']: 
            fir_polygons.append(shape(feature['geometry']))
            
    # CRITICAL BOUNDARY VALIDATION BLOCK
    if not fir_polygons:
        print("[ERROR] No FIR boundaries found in the fetched dataset!")
        return []
        
    min_lon = min(poly.bounds[0] for poly in fir_polygons)
    min_lat = min(poly.bounds[1] for poly in fir_polygons)
    max_lon = max(poly.bounds[2] for poly in fir_polygons)
    max_lat = max(poly.bounds[3] for poly in fir_polygons)
    
    our_coordinates = []
    lat = min_lat
    
    while lat <= max_lat:
        lon = min_lon
        while lon <= max_lon:
            current_point = Point(lon, lat)
            if any(poly.contains(current_point) for poly in fir_polygons):
                our_coordinates.append({
                    "latitude": round(lat, 6),
                    "longitude": round(lon, 6)
                })
            lon += grid_interval
        lat += grid_interval
        
    print(f"[SUCCESS] Airspace grid filtering completed. Generated {len(our_coordinates)} points.")
    return our_coordinates


def fetch_weather_for_grid(coordinates):
    """
    Sends a bulk request to the Open-Meteo API to retrieve winds aloft
    and temperatures for all 12 specified atmospheric pressure levels.
    """
    if not coordinates:
        return {}

    lats = [str(pt["latitude"]) for pt in coordinates]
    lons = [str(pt["longitude"]) for pt in coordinates]
    
    # 12 pressure levels perfectly matching reference flight level schema
    hourly_variables = [
        "temperature_1000hPa", "windspeed_1000hPa", "winddirection_1000hPa", # FL000 / Surface
        "temperature_925hPa", "windspeed_925hPa", "winddirection_925hPa",   # FL025
        "temperature_900hPa", "windspeed_900hPa", "winddirection_900hPa",   # FL030
        "temperature_850hPa", "windspeed_850hPa", "winddirection_850hPa",   # FL050
        "temperature_800hPa", "windspeed_800hPa", "winddirection_800hPa",   # FL064
        "temperature_700hPa", "windspeed_700hPa", "winddirection_700hPa",   # FL100
        "temperature_600hPa", "windspeed_600hPa", "winddirection_600hPa",   # FL140
        "temperature_500hPa", "windspeed_500hPa", "winddirection_500hPa",   # FL180
        "temperature_400hPa", "windspeed_400hPa", "winddirection_400hPa",   # FL240
        "temperature_300hPa", "windspeed_300hPa", "winddirection_300hPa",   # FL300
        "temperature_250hPa", "windspeed_250hPa", "winddirection_250hPa",   # FL340
        "temperature_200hPa", "windspeed_200hPa", "winddirection_200hPa"    # FL390
    ]
    
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": ",".join(lats),
        "longitude": ",".join(lons),
        "hourly": ",".join(hourly_variables),
        "wind_speed_unit": "kn",
        "forecast_days": 1
    }
    
    print("[INFO] Fetching real-time winds aloft data from Open-Meteo API...")
    response = requests.get(url, params=params)
    
    if response.status_code != 200:
        print(f"[ERROR] Open-Meteo API call failed! Status Code: {response.status_code}")
        return {}
        
    return response.json()


def format_to_target_schema(coordinates, raw_api_data):
    """
    Transforms raw dataset into the exact dictionary-based structure 
    matching the target reference dataset specification.
    """
    if not raw_api_data:
        return {}

    if isinstance(raw_api_data, dict) and "hourly" in raw_api_data and not isinstance(raw_api_data, list):
        raw_api_data = [raw_api_data]

    # Generate dynamic timestamp and datestring (e.g., Day 15 + Hour 15 = "1515")
    now_utc = datetime.now(timezone.utc)
    date_iso = now_utc.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    datestring_val = now_utc.strftime("%d%H")

    output_data = {
        "info": {
            "date": date_iso,
            "datestring": datestring_val,
            "legal": "Weather data by Open-Meteo.com (https://open-meteo.com)"
        },
        "data": {}
    }
    
    # Define mapping between reference JSON level keys and Open-Meteo hPa variables
    level_mapping = {
        "0": "1000hPa",
        "25": "925hPa",
        "30": "900hPa",
        "50": "850hPa",
        "64": "800hPa",
        "100": "700hPa",
        "140": "600hPa",
        "180": "500hPa",
        "240": "400hPa",
        "300": "300hPa",
        "340": "250hPa",
        "390": "200hPa"
    }

    # Reconstruct the weather structure matching the target template
    for idx, pt in enumerate(coordinates):
        try:
            hourly_data = raw_api_data[idx]["hourly"]
            
            # Generate short distinct identifier for each grid node (e.g., TRG01, TRG02...)
            point_id = f"TRG{str(idx + 1).zfill(2)}"
            
            node_structure = {
                "coords": {
                    "lat": str(pt["latitude"]),
                    "long": str(pt["longitude"])
                },
                "levels": {}
            }
            
            # Fill out every required aviation flight level block
            for json_lvl, hpa_lvl in level_mapping.items():
                # Extract raw Celsius value and mathematically convert to Kelvin scale
                temp_celsius = hourly_data[f"temperature_{hpa_lvl}"][0]
                temp_kelvin = round(temp_celsius + 273.15, 2)
                
                node_structure["levels"][json_lvl] = {
                    "T(K)": str(temp_kelvin),
                    "windspeed": str(round(hourly_data[f"windspeed_{hpa_lvl}"][0], 1)),
                    "windhdg": str(int(hourly_data[f"winddirection_{hpa_lvl}"][0]))
                }
                
            output_data["data"][point_id] = node_structure
        except (KeyError, IndexError):
            continue
            
    return output_data


if __name__ == "__main__":
    print("====================================================================")
    print("IASsure Data Provisioning Daemon initialized successfully.")
    print("Author/Credit: made by alp-1863530")
    print("Monitoring Frequency: Controlled loop running every 1 hour")
    print("====================================================================")
    
    while True:
        try:
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Starting synchronized weather update cycle...")
            
            # Scan the domestic FIR bounds using the optimal 1.5 spacing matrix
            target_grid = generate_our_fir_grid(grid_interval=1.5)
            
            if target_grid:
                raw_weather = fetch_weather_for_grid(target_grid)
                final_json_data = format_to_target_schema(target_grid, raw_weather)
                
                if final_json_data:
                    # Save output to local deployment folder as a completely minified single-line file
                    with open("weather.json", "w", encoding="utf-8") as out_file:
                        json.dump(final_json_data, out_file, ensure_ascii=False, separators=(',', ':'))
                        
                    print("[SUCCESS] Deployment ready! 'weather.json' successfully generated in exact minified format.")
            
        except Exception as execution_fault:
            # Safe catch-all to keep the script running continuously even during internet outages or timeout issues
            print(f"[FATAL ERROR] Runtime exception caught inside the core worker thread: {execution_fault}")
            
        print(f"[{time.strftime('%H:%M:%S')}] Cycle complete. Sleeping for 3600 seconds (1 hour)...")
        time.sleep(3600)