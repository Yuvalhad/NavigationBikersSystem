from flask import Blueprint, request, jsonify
import mysql.connector
from db.DB import get_db_connection
from work_calculate_ways.geoCoding import geocode_address
from work_calculate_ways.osm import fetch_osm_data_bbox, osm_to_graph, simplify_graph, haversine_distance
from work_calculate_ways.pathFinding import shortest_path, flattest_path, merge_paths
import json
import networkx as nx

api_bp = Blueprint('api', __name__)

@api_bp.route('/register', methods=['POST'])
def register_user():
    data = request.get_json()
    email = data.get('email')
    name = data.get('name')
    password = data.get('password')

    if not (email and name and password):
        return jsonify({"error": "Missing email, name, or password"}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT user_id FROM users WHERE email = %s", (email,))
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({"error": "Email already registered"}), 400

        cursor.execute("INSERT INTO users (email, name, password) VALUES (%s, %s, %s)",
                       (email, name, hashed_password))
        conn.commit()
        user_id = cursor.lastrowid

        cursor.close()
        conn.close()
        return jsonify({"message": "User registered", "user_id": user_id}), 201
    except mysql.connector.Error as err:
        return jsonify({"error": f"Database error: {str(err)}"}), 500

@api_bp.route('/login', methods=['POST'])
def login_user():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if not (email and password):
        return jsonify({"error": "Missing email or password"}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, name, password FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if not user:
            return jsonify({"error": "User not found"}), 404

        user_id, stored_email, stored_password = user
        # בדיקה שהשם והסיסמה תואמים את אלה ששמורים במסד נתונים
        if email == stored_email and password == stored_password:
            return jsonify({"message": "Login successful", "user_id": user_id, "email": email, "name": name}), 200
        else:
            return jsonify({"error": "Invalid name or password"}), 401
    except mysql.connector.Error as err:
        return jsonify({"error": f"Database error: {str(err)}"}), 500

@api_bp.route('/path', methods=['POST'])
def compute_path():
    data = request.get_json()
    start_address = data.get('start_address')
    end_address = data.get('end_address')
    email = data.get('email')
    max_slope = float(data.get('max_slope', float('inf')))

    if not (start_address and end_address and email):
        return jsonify({"error": "Missing start_address, end_address, or email"}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        if not user:
            cursor.close()
            conn.close()
            return jsonify({"error": "User not found"}), 404
        user_id = user[0]
    except mysql.connector.Error as err:
        cursor.close()
        conn.close()
        return jsonify({"error": f"Database error: {str(err)}"}), 500

    start_coords = geocode_address(start_address)
    end_coords = geocode_address(end_address)

    if not start_coords or not end_coords:
        cursor.close()
        conn.close()
        return jsonify({"error": "Could not geocode one or both addresses"}), 400

    start_lat, start_lon = start_coords
    end_lat, end_lon = end_coords

    padding = 0.05
    min_lat = min(start_lat, end_lat) - padding
    max_lat = max(start_lat, end_lat) + padding
    min_lon = min(start_lon, end_lon) - padding
    max_lon = max(start_lon, end_lon) + padding

    osm_data = fetch_osm_data_bbox(min_lat, min_lon, max_lat, max_lon)
    if not osm_data:
        cursor.close()
        conn.close()
        return jsonify({"error": "Failed to fetch OSM data"}), 500

    road_graph, node_data = osm_to_graph(osm_data)
    if not road_graph.nodes:
        cursor.close()
        conn.close()
        return jsonify({"error": "No road data found"}), 500

    def find_closest_node(coord, nodes):
        return min(nodes, key=lambda n: haversine_distance(coord, n))

    start_node = find_closest_node((start_lon, start_lat), road_graph.nodes)
    end_node = find_closest_node((end_lon, end_lat), road_graph.nodes)

    simplified_graph, node_data = simplify_graph(road_graph, node_data, target_nodes=300,
                                                start_node=start_node, goal_node=end_node)
    if not nx.has_path(simplified_graph, start_node, end_node):
        cursor.close()
        conn.close()
        return jsonify({"error": "No path after simplification"}), 500

    shortest = shortest_path(simplified_graph, start_node, end_node)
    flattest = flattest_path(simplified_graph, start_node, end_node, max_slope)

    if not (shortest and flattest):
        cursor.close()
        conn.close()
        return jsonify({"error": f"Could not compute path with slope <= {max_slope:.2f} degrees"}), 500

    merged_graph = merge_paths(shortest, flattest, simplified_graph, node_data, start_node, end_node)

    final_path = shortest_path(merged_graph, start_node, end_node)
    if not final_path:
        cursor.close()
        conn.close()
        return jsonify({"error": "No merged path found"}), 500

    total_slope = sum(simplified_graph.edges[u, v]["slope"] for u, v in zip(final_path[:-1], final_path[1:]) if
                      simplified_graph.has_edge(u, v))

    path_coords = [{"latitude": node_data[node]["latitude"], "longitude": node_data[node]["longitude"]}
                   for node in final_path]

    try:
        cursor.execute('''
            INSERT INTO routes (start_lat, start_lon, end_lat, end_lon, user_id, max_slope, total_slope)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        ''', (start_lat, start_lon, end_lat, end_lon, user_id, max_slope, total_slope))
        route_id = cursor.lastrowid

        cursor.execute('''
            INSERT INTO route_paths (route_id, path_json)
            VALUES (%s, %s)
        ''', (route_id, json.dumps(path_coords)))

        conn.commit()
    except mysql.connector.Error as err:
        conn.rollback()
        cursor.close()
        conn.close()
        return jsonify({"error": f"Database error: {str(err)}"}), 500
    finally:
        cursor.close()
        conn.close()

    return jsonify({
        "path": path_coords,
        "total_slope": total_slope,
        "route_id": route_id,
        "message": f"Path found with total slope of {total_slope:.2f} degrees"
    })