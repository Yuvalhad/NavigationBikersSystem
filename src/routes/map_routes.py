from flask import Blueprint, render_template
from db.DB import get_db_connection
from work_calculate_ways.osm import osm_to_graph,fetch_osm_data_bbox
import requests
import json

map_bp = Blueprint('map', __name__)

@map_bp.route('/view_path/<int:route_id>', methods=['GET'])
def view_path(route_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT r.start_lat, r.start_lon, r.end_lat, r.end_lon, r.max_slope, r.total_slope, rp.path_json "
                   "FROM routes r JOIN route_paths rp ON r.route_id = rp.route_id WHERE r.route_id = %s", (route_id,))
    route = cursor.fetchone()
    cursor.close()
    conn.close()

    if not route:
        return "מסלול לא נמצא", 404

    path_coords = json.loads(route['path_json'])

    # קבל נתוני OSM עבור אזור המסלול
    start_lat, start_lon = route['start_lat'], route['start_lon']
    end_lat, end_lon = route['end_lat'], route['end_lon']
    # חשב גבולות (bounding box) סביב המסלול
    lat_min = min(start_lat, end_lat) - 0.01
    lat_max = max(start_lat, end_lat) + 0.01
    lon_min = min(start_lon, end_lon) - 0.01
    lon_max = max(start_lon, end_lon) + 0.01

    osm_data = fetch_osm_data_bbox(lat_min, lon_min, lat_max, lon_max)
    if not osm_data:
     return "❌ Cant load Overpass API", 500

    G, node_data = osm_to_graph(osm_data)

    # המר את ה-Graph לפורמט JSON
    graph_data = {
        "nodes": [],
        "edges": []
    }

    # התאם את הפורמט של הצמתים למה ש-`view_path.html` מצפה
    for node in G.nodes(data=True):
        node_id = str(node[0])  # המר ל-string כי node הוא טאפל (lon, lat)
        node_info = node_data[node[0]]  # קבל את המידע ממילון node_data
        lat = node_info.get('latitude')
        lon = node_info.get('longitude')
        if lat is not None and lon is not None:
            graph_data["nodes"].append({"id": node_id, "lat": lat, "lon": lon})

    for edge in G.edges(data=True):
        node1, node2 = edge[0], edge[1]
        node1_data = node_data[node1]
        node2_data = node_data[node2]
        lat1, lon1 = node1_data.get('latitude'), node1_data.get('longitude')
        lat2, lon2 = node2_data.get('latitude'), node2_data.get('longitude')
        if lat1 and lon1 and lat2 and lon2:
            graph_data["edges"].append({
                "from": {"lat": lat1, "lon": lon1},
                "to": {"lat": lat2, "lon": lon2}
            })

    return render_template('view_path.html', path_coords=path_coords, max_slope=route['max_slope'], graph_data=graph_data)