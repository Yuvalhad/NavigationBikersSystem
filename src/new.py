import json
import math
import re


# פתרון 1: עיגול קואורדינטות לדיוק קבוע
def normalize_coordinate(coord, precision=3):
    return round(coord, precision)


def get_elevation_by_exact_match(lat, lon, elevation_data):
    """חיפוש גובה לפי התאמה מדויקת עם נירמול"""
    normalized_lat = normalize_coordinate(lat)
    normalized_lon = normalize_coordinate(lon)
    key = f"({normalized_lat}, {normalized_lon})"

    return elevation_data.get(key)


# פתרון 2: חיפוש הקואורדינטה הקרובה ביותר
def get_elevation_by_closest_match(target_lat, target_lon, elevation_data):
    """חיפוש הקואורדינטה הקרובה ביותר"""
    min_distance = float('inf')
    closest_elevation = None
    closest_coord = None

    for coord_key, elevation in elevation_data.items():
        # חילוץ קואורדינטות מהמפתח
        match = re.match(r'\(([^,]+),\s*([^)]+)\)', coord_key)
        if not match:
            continue

        lat = float(match.group(1))
        lon = float(match.group(2))

        # חישוב מרחק (אוקלידי פשוט)
        distance = math.sqrt((target_lat - lat) ** 2 + (target_lon - lon) ** 2)

        if distance < min_distance:
            min_distance = distance
            closest_elevation = elevation
            closest_coord = coord_key

    return {
        'elevation': closest_elevation,
        'coordinate': closest_coord,
        'distance': min_distance
    }


# פתרון 3: פונקציה מאוחדת עם fallback
def get_elevation(lat, lon, elevation_data, tolerance=0.001):
    """פונקציה מאוחדת לחיפוש גובה עם fallback"""
    # ניסיון ראשון: חיפוש מדויק עם נירמול
    elevation = get_elevation_by_exact_match(lat, lon, elevation_data)

    if elevation is not None:
        return {
            'elevation': elevation,
            'method': 'exact',
            'coordinate': f"({normalize_coordinate(lat)}, {normalize_coordinate(lon)})"
        }

    # ניסיון שני: חיפוש הקואורדינטה הקרובה ביותר
    closest = get_elevation_by_closest_match(lat, lon, elevation_data)

    if closest['elevation'] is not None and closest['distance'] <= tolerance:
        return {
            'elevation': closest['elevation'],
            'method': 'closest',
            'coordinate': closest['coordinate'],
            'distance': closest['distance']
        }

    return {
        'elevation': None,
        'method': 'not_found',
        'coordinate': f"({lat}, {lon})",
        'message': 'לא נמצא גובה עבור קואורדינטה זו'
    }


# פונקציה לעיבוד רשימת קואורדינטות
def process_coordinates_list(coordinates, elevation_data):
    """עיבוד רשימת קואורדינטות והחזרת התוצאות"""
    results = []

    for coord in coordinates:
        result = get_elevation(coord['lat'], coord['lon'], elevation_data)
        results.append({
            'original_lat': coord['lat'],
            'original_lon': coord['lon'],
            **result
        })

    return results


# פונקציה לטעינת נתונים מקובץ JSON
def load_elevation_data(file_path):
    """טעינת נתוני גובה מקובץ JSON"""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return json.load(file)
    except FileNotFoundError:
        print(f"קובץ {file_path} לא נמצא")
        return {}
    except json.JSONDecodeError:
        print(f"שגיאה בקריאת קובץ JSON: {file_path}")
        return {}


# דוגמה לשימוש:
if __name__ == "__main__":
    # נתוני דוגמה
    elevation_data = {
        "(34.586042, 31.664292)": 47.0,
        "(34.123456, 31.789012)": 120.5,
        # יש להוסיף כאן את שאר הנתונים מהקובץ
    }

    # דוגמת קואורדינטות לבדיקה
    coordinates_to_check = [
        {'lat': 34.586042, 'lon': 31.6642924},  # הקואורדינטה הבעייתית
        {'lat': 34.586042, 'lon': 31.664292},  # קואורדינטה מדויקת
        {'lat': 34.123456, 'lon': 31.789012},  # עוד קואורדינטה מדויקת
        {'lat': 34.111111, 'lon': 31.222222},  # קואורדינטה שלא קיימת
    ]

    # עיבוד הקואורדינטות
    results = process_coordinates_list(coordinates_to_check, elevation_data)

    # הדפסת התוצאות
    for i, result in enumerate(results, 1):
        print(f"קואורדינטה {i}:")
        print(f"  מקורית: ({result['original_lat']}, {result['original_lon']})")
        print(f"  גובה: {result['elevation'] if result['elevation'] is not None else 'לא נמצא'}")
        print(f"  שיטה: {result['method']}")
        if 'distance' in result:
            print(f"  מרחק מהקואורדינטה הקרובה: {result['distance']:.8f}")
        if 'message' in result:
            print(f"  הודעה: {result['message']}")
        print("---")

    # טעינה מקובץ (הסר הערה כשיש לך קובץ)
    # elevation_data_from_file = load_elevation_data('elevation.json')
    # results_from_file = process_coordinates_list(coordinates_to_check, elevation_data_from_file)


# פונקציות עזר נוספות:

def find_missing_coordinates(coordinates_list, elevation_data):
    """מציאת קואורדינטות שחסר להן גובה"""
    missing = []
    for coord in coordinates_list:
        result = get_elevation(coord['lat'], coord['lon'], elevation_data)
        if result['elevation'] is None:
            missing.append(coord)
    return missing


def get_elevation_statistics(elevation_data):
    """סטטיסטיקות על נתוני הגובה"""
    elevations = [v for v in elevation_data.values() if v is not None]
    if not elevations:
        return None

    return {
        'count': len(elevations),
        'min': min(elevations),
        'max': max(elevations),
        'avg': sum(elevations) / len(elevations)
    }


def export_results_to_csv(results, filename='elevation_results.csv'):
    """יצוא התוצאות לקובץ CSV"""
    import csv

    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['original_lat', 'original_lon', 'elevation', 'method', 'coordinate', 'distance']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        writer.writeheader()
        for result in results:
            # הכנת השורה עם רק השדות הרלוונטיים
            row = {k: result.get(k, '') for k in fieldnames}
            writer.writerow(row)