import requests

def get_bbox_from_city_name(city_name):
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": city_name,
        "format": "json",
        "limit": 1,
        "countrycodes": "il",
        "addressdetails": 1,
        "polygon_geojson": 0,
        "extratags": 0
    }
    headers = {
        "User-Agent": "BikeRoutePlanner/1.0 (yhad890@gmail.com)"
    }

    try:
        response = requests.get(url, params=params, headers=headers, timeout=5)
        data = response.json()
        if response.status_code == 200 and data:
            bbox = data[0]["boundingbox"]  # [south_lat, north_lat, west_lon, east_lon]
            min_lat, max_lat = float(bbox[0]), float(bbox[1])
            min_lon, max_lon = float(bbox[2]), float(bbox[3])
            return min_lat, min_lon, max_lat, max_lon
        else:
            print(f"❌ No bounding box found for {city_name}")
            return None
    except Exception as e:
        print(f"❌ Error fetching bbox for {city_name}: {str(e)}")
        return None

def geocode_address(address):
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": address,
        "format": "json",
        "limit": 1,
        "countrycodes": "il"
    }
    headers = {
        "User-Agent": "BikeRoutePlanner/1.0 (yhad890@gmail.com)"
    }
    try:
        response = requests.get(url, params=params, headers=headers, timeout=5)
        if response.status_code == 200 and response.json():
            result = response.json()[0]
            return float(result["lat"]), float(result["lon"])
        else:
            print(f"❌ Geocoding failed for {address}: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Geocoding error for {address}: {str(e)}")
        return None