import ast
import networkx as nx
import heapq
import math
from work_calculate_ways.geoCoding import (geocode_address,get_bbox_from_city_name)
from work_calculate_ways.osm import (haversine_distance,
                                     calculate_slope,
                                     osm_to_graph,
                                     fetch_osm_data_bbox,
                                     connect_to_nearest_node,
                                     simplify_graph,
                                     fetch_elevation_data)
import json
from city import city_name

G = None
node_data = None

def init_graph_from_city():
    global G, node_data
    print(f"📍 Using city_name: {city_name}")
    bbox = get_bbox_from_city_name(city_name)
    if not bbox or len(bbox) != 4:
        raise ValueError(f"❌ No bounding box found for '{city_name}'")
    min_lat, min_lon, max_lat, max_lon = bbox
    osm_data = fetch_osm_data_bbox(min_lat, min_lon, max_lat, max_lon)
    G, node_data = osm_to_graph(osm_data)
    G, node_data = simplify_graph(G, node_data, target_nodes=300)

def shortest_path(G, start, goal):
    if start not in G or goal not in G:
        print("⚠️ Adding start or goal node to graph since not found.")
        G.add_node(start)
        G.add_node(goal)
    open_set = [(0, start, [start])]
    g_score = {start: 0}
    f_score = {start: haversine_distance(start, goal)}
    while open_set:
        _, current, path = heapq.heappop(open_set)
        if current == goal:
            print(f"✅ Found shortest path with {len(path)} nodes")
            return path
        for neighbor in G.neighbors(current):
            edge_distance = G.edges[current, neighbor]["distance"]
            tentative_g_score = g_score.get(current, float('inf')) + edge_distance
            if tentative_g_score < g_score.get(neighbor, float('inf')):
                new_path = path + [neighbor]
                g_score[neighbor] = tentative_g_score
                f_score[neighbor] = tentative_g_score + haversine_distance(neighbor, goal)
                heapq.heappush(open_set, (f_score[neighbor], neighbor, new_path))
    print("❌ No path found.")
    return None

def normalize_coordinate(coord):
    """Normalize a coordinate tuple by rounding lat and lon to 3 decimal places."""
    return (round(coord[0], 3), round(coord[1], 3))

def get_elevation_by_exact_match(node, elevation_dict):
    """Try to get elevation by exact coordinate match."""
    norm_node = normalize_coordinate(node)
    return elevation_dict.get(norm_node, None)

def get_elevation_by_closest_match(node, elevation_dict):
    """Find the closest elevation point in elevation_dict to the given node."""
    min_dist = float('inf')
    closest_elev = None
    for coord, elev in elevation_dict.items():
        dist = haversine_distance(node, coord)
        if dist < min_dist:
            min_dist = dist
            closest_elev = elev
    return closest_elev

def get_elevation_smart(node, elevation_dict):
    """Get elevation using smart lookup with exact and closest match fallback."""
    elev = get_elevation_by_exact_match(node, elevation_dict)
    if elev is not None:
        return elev
    elev = get_elevation_by_closest_match(node, elevation_dict)
    if elev is not None:
        return elev
    return 0  # fallback if no elevation found

def extract_coordinates_from_node(node):
    """Extract coordinates from a node which might be a tuple or other structure."""
    if isinstance(node, tuple) and len(node) == 2 and all(isinstance(x, (int, float)) for x in node):
        return node
    # Add more extraction logic if node structure changes
    return node

def flattest_path(G, start, goal, max_slope=float('inf'), elevation_dict=None):
    if start not in G or goal not in G:
        print("⚠️ Adding start or goal node to graph since not found.")
        G.add_node(start)
        G.add_node(goal)

    # ⬅️ עדכן elevation לכל node מה־elevation_dict
    if elevation_dict:
        for node in G.nodes:
            if node in elevation_dict:
                G.nodes[node]["elevation"] = elevation_dict[node]
            else:
                print(f"⚠️ Missing elevation for node {node}")
                G.nodes[node]["elevation"] = 0

    # Assign elevations smartly to nodes
    for node in G.nodes:
        elev = get_elevation_smart(node, elevation_dict)
        G.nodes[node]["elevation"] = elev

    # Normalize elevation values for slope calculation
    elevations = [G.nodes[node]["elevation"] for node in G.nodes]
    min_elev = min(elevations) if elevations else 0
    max_elev = max(elevations) if elevations else 0
    elev_range = max_elev - min_elev if max_elev != min_elev else 1

    # Assign normalized elevation to nodes
    for node in G.nodes:
        norm_elev = (G.nodes[node]["elevation"] - min_elev) / elev_range
        G.nodes[node]["norm_elevation"] = norm_elev

    # ⬅️ חשב ושמור slope לכל edge
    for u, v in G.edges():
        elev_u = G.nodes[u].get("norm_elevation", 0)
        elev_v = G.nodes[v].get("norm_elevation", 0)
        dist = G.edges[u, v].get("distance", haversine_distance(u, v))
        if dist == 0:
            slope = 0
        else:
            slope = abs(elev_v - elev_u) / dist
        # Convert slope to degrees for consistency with other functions
        slope_degrees = math.degrees(math.atan(slope))  # convert slope (rise/run) to degrees
        G.edges[u, v]["slope"] = slope_degrees

    # ⬅️ חיפוש במסלול לפי שיפוע מצטבר
    open_set = [(0, start, [start])]
    g_score = {start: 0}
    f_score = {start: 0}
    while open_set:
        _, current, path = heapq.heappop(open_set)
        if current == goal:
            slopes = [G.edges[u, v]["slope"] for u, v in zip(path[:-1], path[1:]) if G.has_edge(u, v)]
            for i, (u, v) in enumerate(zip(path[:-1], path[1:])):
                if G.has_edge(u, v):
                    print(f"↪️ Segment {i + 1}: {u} -> {v}, slope = {G.edges[u, v]['slope']:.2f}°")
            if slopes:
                max_slope_in_path = max(slopes)
                print(f"✅ Found flattest path. Max segment slope: {max_slope_in_path:.2f}°, Total segments: {len(slopes)}")
            else:
                print("⚠️ No slopes found for path segments.")
            return path

        for neighbor in G.neighbors(current):
            if "slope" not in G.edges[current, neighbor]:
                continue  # אם אין שיפוע בקשת, דלג
            edge_slope = G.edges[current, neighbor]["slope"]
            if edge_slope > max_slope:
                continue
            tentative_g_score = g_score.get(current, float('inf')) + edge_slope
            if tentative_g_score < g_score.get(neighbor, float('inf')):
                new_path = path + [neighbor]
                g_score[neighbor] = tentative_g_score
                f_score[neighbor] = tentative_g_score
                heapq.heappush(open_set, (f_score[neighbor], neighbor, new_path))

    print(f"❌ No path found with slope <= {max_slope:.2f} degrees.")
    return None


def merge_paths(shortest_path, flattest_path, G, node_data, start_node, goal_node):
    merged_graph = nx.Graph()
    shortest_edges = [(shortest_path[i], shortest_path[i + 1]) for i in range(len(shortest_path) - 1)]
    flattest_edges = [(flattest_path[i], flattest_path[i + 1]) for i in range(len(flattest_path) - 1)]
    common_edges = set(shortest_edges).intersection(flattest_edges)
    print(f"🔗 Found {len(common_edges)} common edges")

    for edge in common_edges:
        u, v = edge
        merged_graph.add_edge(u, v)
        if G.has_edge(u, v):
            merged_graph.edges[u, v]["distance"] = G.edges[u, v]["distance"]
            merged_graph.edges[u, v]["slope"] = G.edges[u, v]["slope"]
            merged_graph.edges[u, v]["streets"] = G.edges[u, v]["streets"]
        merged_graph.edges[u, v]["is_path"] = True

    shortest_unique = set(shortest_edges) - common_edges
    flattest_unique = set(flattest_edges) - common_edges
    unique_edges = shortest_unique.union(flattest_unique)

    for edge in unique_edges:
        u, v = edge
        slope = G.edges[u, v]["slope"] if G.has_edge(u, v) else calculate_slope(
            u, v, node_data[u]["elevation"], node_data[v]["elevation"]
        )
        distance = G.edges[u, v]["distance"] if G.has_edge(u, v) else haversine_distance(u, v)
        merged_graph.add_edge(u, v, slope=slope, distance=distance)
        if G.has_edge(u, v):
            merged_graph.edges[u, v]["streets"] = G.edges[u, v]["streets"]
        merged_graph.edges[u, v]["is_path"] = False

    for node in list(merged_graph.nodes):
        if merged_graph.degree(node) > 2:
            neighbors = list(merged_graph.neighbors(node))
            for i in range(len(neighbors)):
                for j in range(i + 1, len(neighbors)):
                    edge1 = (node, neighbors[i]) if (node, neighbors[i]) in merged_graph.edges else (neighbors[i], node)
                    edge2 = (node, neighbors[j]) if (node, neighbors[j]) in merged_graph.edges else (neighbors[j], node)
                    if edge1 in merged_graph.edges and edge2 in merged_graph.edges:
                        slope1 = merged_graph.edges[edge1]["slope"]
                        distance1 = merged_graph.edges[edge1]["distance"]
                        combined_weight1 = 0.9 * slope1 + 0.1 * distance1
                        slope2 = merged_graph.edges[edge2]["slope"]
                        distance2 = merged_graph.edges[edge2]["distance"]
                        combined_weight2 = 0.9 * slope2 + 0.1 * distance2
                        if combined_weight1 > combined_weight2:
                            merged_graph.edges[edge1]["is_path"] = False
                            merged_graph.edges[edge2]["is_path"] = True
                        else:
                            merged_graph.edges[edge1]["is_path"] = True
                            merged_graph.edges[edge2]["is_path"] = False

    preferred_graph = nx.Graph()
    for u, v, data in merged_graph.edges(data=True):
        if data["is_path"]:
            preferred_graph.add_edge(u, v, **data)

    path_exists = False
    if preferred_graph.has_node(start_node) and preferred_graph.has_node(goal_node):
        try:
            path = nx.shortest_path(preferred_graph, start_node, goal_node, weight="slope")
            path_exists = True
        except nx.NetworkXNoPath:
            print("⚠️ No path between start and goal with preferred edges only. Connecting subgraphs...")

    if not path_exists:
        components = list(nx.connected_components(preferred_graph))
        print(f"⚠️ Found {len(components)} disconnected components")
        node_to_component = {}
        for idx, component in enumerate(components):
            for node in component:
                node_to_component[node] = idx

        if start_node not in preferred_graph:
            preferred_graph.add_node(start_node)
            node_to_component[start_node] = len(components)
            components.append({start_node})
        if goal_node not in preferred_graph:
            preferred_graph.add_node(goal_node)
            node_to_component[goal_node] = len(components)
            components.append({goal_node})

        component_graph = nx.Graph()
        for idx in range(len(components)):
            component_graph.add_node(idx)

        all_edges = set(shortest_edges).union(flattest_edges)
        for u, v in all_edges:
            if u in node_to_component and v in node_to_component:
                comp_u = node_to_component[u]
                comp_v = node_to_component[v]
                if comp_u != comp_v:
                    if merged_graph.has_edge(u, v):
                        slope = merged_graph.edges[u, v]["slope"]
                        component_graph.add_edge(comp_u, comp_v, u=u, v=v, slope=slope,
                                                distance=merged_graph.edges[u, v]["distance"])

        start_component = node_to_component.get(start_node, None)
        goal_component = node_to_component.get(goal_node, None)

        if start_component is None or goal_component is None:
            print("⚠️ Start or goal node not in any component. Falling back to shortest path...")
            for u, v in shortest_edges:
                if merged_graph.has_edge(u, v):
                    merged_graph.edges[u, v]["is_path"] = True
        else:
            open_set = [(0, start_component, [start_component])]
            g_score = {start_component: 0}
            f_score = {start_component: 0}
            came_from = {}
            while open_set:
                _, current, path = heapq.heappop(open_set)
                if current == goal_component:
                    break
                for neighbor in component_graph.neighbors(current):
                    edge_data = component_graph.edges[current, neighbor]
                    slope = edge_data["slope"]
                    tentative_g_score = g_score.get(current, float('inf')) + slope
                    if tentative_g_score < g_score.get(neighbor, float('inf')):
                        came_from[neighbor] = (current, edge_data["u"], edge_data["v"])
                        g_score[neighbor] = tentative_g_score
                        f_score[neighbor] = tentative_g_score
                        heapq.heappush(open_set, (f_score[neighbor], neighbor, path + [neighbor]))

            current = goal_component
            while current in came_from:
                prev_component, u, v = came_from[current]
                if merged_graph.has_edge(u, v):
                    merged_graph.edges[u, v]["is_path"] = True
                current = prev_component

    print(f"✅ Merged graph: {merged_graph.number_of_nodes()} nodes, {merged_graph.number_of_edges()} edges")

    # שמירת הגרף לקובץ JSON
    graph_data = {
        "nodes": [{"id": str(node), "coords": node} for node in merged_graph.nodes],
        "edges": [{"source": str(u), "target": str(v), "is_path": data["is_path"]} for u, v, data in merged_graph.edges(data=True)]
    }
    with open("merged_graph.json", "w", encoding="utf-8") as f:
        json.dump(graph_data, f, ensure_ascii=False, indent=2)
    print("💾 Saved merged graph to merged_graph.json")

    return merged_graph

def get_merged_route(start_address, end_address, max_slope=float('inf')):
    """קבלת מסלול ממוזג על בסיס כתובות עם שיפוע מרבי."""
    # ודא שהגרף מאותחל לפני שממשיכים
    global G, node_data
    if G is None or node_data is None:
        init_graph_from_city()

    start_coords = geocode_address(start_address)
    end_coords = geocode_address(end_address)

    if not start_coords or not end_coords:
        print("❌ Failed to geocode one or both addresses.")
        return None

    start_node = start_coords
    goal_node = end_coords

    if start_node not in G:
        connect_to_nearest_node(G, node_data, start_node)
    else:
        print("✅ start_node already in graph")

    if goal_node not in G:
        connect_to_nearest_node(G, node_data, goal_node)
    else:
        print("✅ goal_node already in graph")

    with open("elevation.json", "r") as f:
        raw_elevation_data = json.load(f)

    elevation_dict = {ast.literal_eval(k): v for k, v in raw_elevation_data.items()}

    shortest = shortest_path(G, start_node, goal_node)
    flattest = flattest_path(G, start_node, goal_node, max_slope,elevation_dict)

    if shortest and flattest:
        merged_graph = merge_paths(shortest, flattest, G, node_data, start_node, goal_node)
        try:
            final_path = nx.shortest_path(merged_graph, start_node, goal_node, weight="slope")
            return [(node[0], node[1]) if isinstance(node, tuple) else node for node in final_path]
        except nx.NetworkXNoPath:
            print("❌ No final path found in merged graph.")
            return None
    return None