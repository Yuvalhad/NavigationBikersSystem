import requests
import networkx as nx
from math import sqrt, radians, sin, cos, asin, degrees, atan

import city
from city import city_name
import os
import json
import time

def fetch_osm_data_bbox(min_lat, min_lon, max_lat, max_lon):
    query = f"""
    [out:json];
    (
      way["highway"~"cycleway|residential|tertiary|secondary|primary"]
      ["bicycle"!~"no"]
      ["access"!~"private"]({min_lat},{min_lon},{max_lat},{max_lon});
    );
    out geom;
    """
    response = requests.get("http://overpass-api.de/api/interpreter", params={"data": query})
    if response.status_code == 200:
        return response.json()
    else:
        print("❌ Failed to fetch data:", response.text)
        return None

def fetch_elevation_data(coords):
    url = "https://api.open-elevation.com/api/v1/lookup"
    results = {}
    if os.path.exists("elevation.json"):
        with open("elevation.json", "r") as f:
            existing_data = json.load(f)
    else:
        existing_data = {}
    def chunked(lst, size=1000):
        for i in range(0, len(lst), size):
            yield lst[i:i + size]

    for batch in chunked(coords, 1000):
        locations = [{"latitude": lat, "longitude": lon} for lon, lat in batch]
        try:
            print(f"🌍 Fetching elevation for {len(locations)} points...")
            response = requests.post(url, json={"locations": locations}, timeout=10)
            if response.status_code == 200:
                data = response.json().get("results", [])
                for item in data:
                    coord = (item["longitude"], item["latitude"])
                    results[coord] = item["elevation"]
                    existing_data[str(coord)] = item["elevation"]
                print(f"✅ Successfully fetched {len(data)} elevations.")
            else:
                print(f"❌ Failed to fetch elevation data (status {response.status_code}):", response.text)
        except Exception as e:
            print("❌ Elevation API error:", str(e))
        with open("elevation.json", "w") as f:
            json.dump(existing_data, f)

        time.sleep(1)  # Delay to avoid getting blocked

    return results

def haversine_distance(coord1, coord2):
    lon1, lat1 = map(radians, coord1)
    lon2, lat2 = map(radians, coord2)
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    r = 6371000
    return c * r

def calculate_slope(coord1, coord2, elevation1, elevation2):
    horizontal_distance = haversine_distance(coord1, coord2)
    elevation_diff = abs(elevation2 - elevation1)
    if horizontal_distance == 0:
        return 0.0
    slope_angle = degrees(atan(elevation_diff / horizontal_distance))
    return slope_angle

def osm_to_graph(osm_data):
    G = nx.Graph()
    node_data = {}
    if "elements" not in osm_data:
        print("❌ No road data found!")
        return G, node_data

    all_coords = set()
    for element in osm_data["elements"]:
        if element["type"] == "way" and "geometry" in element:
            for coord in element["geometry"]:
                all_coords.add((coord["lon"], coord["lat"]))

    elevation_data = fetch_elevation_data(list(all_coords))

    for element in osm_data["elements"]:
        if element["type"] == "way" and "geometry" in element:
            street_name = element.get("tags", {}).get("name", "unknown")
            highway_type = element.get("tags", {}).get("highway", "unknown")
            nodes = []
            for coord in element["geometry"]:
                node = (coord["lon"], coord["lat"])
                if node not in G:
                    elevation = elevation_data.get(node, 0.0)
                    G.add_node(node)
                    node_data[node] = {
                        "latitude": coord["lat"],
                        "longitude": coord["lon"],
                        "elevation": elevation,
                        "streets": set(),
                        "highway": highway_type
                    }
                node_data[node]["streets"].add(street_name)
                nodes.append(node)

            for i in range(len(nodes) - 1):
                if G.has_edge(nodes[i], nodes[i + 1]):
                    if "streets" not in G.edges[nodes[i], nodes[i + 1]]:
                        G.edges[nodes[i], nodes[i + 1]]["streets"] = set()
                    G.edges[nodes[i], nodes[i + 1]]["streets"].add(street_name)
                else:
                    G.add_edge(nodes[i], nodes[i + 1], streets={street_name})

    for u, v in G.edges():
        distance = haversine_distance(u, v)
        elev_diff = abs(node_data[v]["elevation"] - node_data[u]["elevation"])
        slope = calculate_slope(u, v, node_data[u]["elevation"], node_data[v]["elevation"])
        weight = distance + elev_diff * 9
        G.edges[u, v]["distance"] = distance
        G.edges[u, v]["slope"] = slope
        G.edges[u, v]["weight"] = weight

    print(f"✅ Built graph with {G.number_of_nodes()} nodes and {G.number_of_edges()} edges")
    return G, node_data

def simplify_graph(G, node_data, target_nodes=300, start_node=None, goal_node=None):
    to_remove = []
    remaining_nodes = G.number_of_nodes()
    distance_threshold = 0.0001

    while remaining_nodes > target_nodes:
        print(f"Current nodes: {remaining_nodes}, targeting {target_nodes}")
        removed_in_this_pass = False

        for node in list(G.nodes):
            if node == start_node or node == goal_node:
                continue
            degree = G.degree(node)
            if degree == 2:
                neighbors = list(G.neighbors(node))
                if len(neighbors) != 2:
                    continue
                edge1_streets = G.edges[node, neighbors[0]]["streets"]
                edge2_streets = G.edges[node, neighbors[1]]["streets"]
                common_streets = edge1_streets.intersection(edge2_streets)

                if common_streets:
                    pos1 = neighbors[0]
                    pos2 = neighbors[1]
                    dist = sqrt((pos2[0] - pos1[0]) ** 2 + (pos2[1] - pos1[1]) ** 2)
                    if dist < distance_threshold:
                        new_distance = haversine_distance(pos1, pos2)
                        new_elev_diff = abs(node_data[pos2]["elevation"] - node_data[pos1]["elevation"])
                        new_slope = calculate_slope(pos1, pos2, node_data[pos1]["elevation"],
                                                   node_data[pos2]["elevation"])
                        new_weight = new_distance + new_elev_diff * 9
                        G.add_edge(pos1, pos2, streets=common_streets, distance=new_distance, slope=new_slope,
                                   weight=new_weight)
                        to_remove.append(node)
                        removed_in_this_pass = True

        if start_node and goal_node and removed_in_this_pass:
            temp_graph = G.copy()
            temp_graph.remove_nodes_from(to_remove)
            if not nx.has_path(temp_graph, start_node, goal_node):
                print(f"⚠️ Removing {len(to_remove)} nodes would disconnect the path. Skipping...")
                removed_in_this_pass = False
            else:
                for node in to_remove:
                    if node in node_data:
                        del node_data[node]

        if not removed_in_this_pass:
            print("⚠️ No more nodes to remove. Increasing threshold...")
            distance_threshold *= 2
            if distance_threshold > 0.05:
                print("⚠️ Maximum threshold reached. Stopping.")
                break

        if removed_in_this_pass:
            G.remove_nodes_from(to_remove)
            remaining_nodes = G.number_of_nodes()
            print(f"Removed {len(to_remove)} nodes. Remaining: {remaining_nodes}")
            to_remove = []

    if not nx.is_connected(G):
        largest_component = max(nx.connected_components(G), key=len)
        G = G.subgraph(largest_component).copy()
        nodes_to_keep = set(G.nodes)
        node_data = {k: v for k, v in node_data.items() if k in nodes_to_keep}

    to_remove_endpoints = []
    for node in G.nodes:
        if node == start_node or node == goal_node:
            continue
        if G.degree(node) == 1:
            neighbors = list(G.neighbors(node))
            if len(neighbors) == 1 and G.degree(neighbors[0]) <= 2:
                to_remove_endpoints.append(node)
    G.remove_nodes_from(to_remove_endpoints)
    for node in to_remove_endpoints:
        if node in node_data:
            del node_data[node]

    print(f"✅ Final nodes: {G.number_of_nodes()}")
    return G, node_data

def connect_to_nearest_node(G, node_data, point):
    closest = min(G.nodes, key=lambda n: haversine_distance(n, point))
    elev1 = node_data.get(point, {}).get("elevation", 0.0)
    elev2 = node_data[closest]["elevation"]
    slope = calculate_slope(point, closest, elev1, elev2)
    distance = haversine_distance(point, closest)
    weight = distance + abs(elev2 - elev1) * 9

    G.add_node(point)
    node_data[point] = {
        "latitude": point[1],
        "longitude": point[0],
        "elevation": elev1,
        "streets": set(["virtual"]),
        "highway": "virtual"
    }
    G.add_edge(point, closest, distance=distance, slope=slope, weight=weight, streets=set(["virtual"]))