from flask import Flask, send_from_directory, request, jsonify
import work_calculate_ways.pathFinding as pathFinding
import json
from routes.api_routes import api_bp
from routes.map_routes import map_bp
import city

app = Flask(__name__)

# רישום ה-Blueprints
app.register_blueprint(api_bp, url_prefix='/api')
app.register_blueprint(map_bp)

# נתיב לשרת את ה-favicon
@app.route('/favicon.ico')
def favicon():
    return send_from_directory('.', 'favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.route('/', methods=['GET'])
def index():
    print("Rendering HTML for root endpoint")
    return '''
    <!DOCTYPE html>
    <html lang="he">
    <head>
        <meta charset="UTF-8">
        <title>מפה פשוטה</title>
        <link rel="icon" type="image/x-icon" href="/favicon.ico">
        <link href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" rel="stylesheet"/>
        <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
        <style>
            #osm-map { height: 600px; width: 100%; border: 1px solid black; }
            body { margin: 0; padding: 0; }
            .input-container { padding: 10px; text-align: right; }
            label { margin-left: 5px; }
            input { margin: 5px; padding: 5px; width: 200px; }
            button { padding: 5px 10px; }
        </style>
    </head>
    <body>
        <h1>מפה בסיסית</h1>
        <div class="input-container">
            <label for="email">אימייל:</label>
            <input type="email" id="email" placeholder="הזן אימייל">
            <br>
            <label for="start-point">נקודת התחלה:</label>
            <input type="text" id="start-point" placeholder="הזן נקודת התחלה (רחוב, עיר)">
            <br>
            <label for="end-point">נקודת סיום:</label>
            <input type="text" id="end-point" placeholder="הזן נקודת סיום (רחוב, עיר)">
            <br>
            <label for="max-slope">שיפוע מרבי (0-270 מעלות):</label>
            <input type="number" id="max-slope" min="0" max="270" value="90">
            <br>
            <button onclick="calculateRoute()">חפש מסלול</button>
        </div>
        <div id="osm-map"></div>
        <script>
            console.log("Starting map initialization");
            var map = L.map('osm-map').setView([32.0853, 34.7818], 13);
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '© OpenStreetMap contributors'
            }).addTo(map);

            function calculateRoute() {
                var email = document.getElementById('email').value;
                var start = document.getElementById('start-point').value;
                var end = document.getElementById('end-point').value;
                var maxSlope = document.getElementById('max-slope').value;
                fetch('/api/path', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ email: email, start_address: start, end_address: end, max_slope: maxSlope })
                })
                .then(response => response.json())
                .then(data => {
                    if (data.path) {
                        if (map) map.remove();
                        map = L.map('osm-map').setView([(data.path[0].latitude + data.path[data.path.length - 1].latitude) / 2, (data.path[0].longitude + data.path[data.path.length - 1].longitude) / 2], 13);
                        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                            attribution: '© OpenStreetMap contributors'
                        }).addTo(map);
                        var pathCoords = data.path.map(coord => [coord.latitude, coord.longitude]);
                        L.polyline(pathCoords, {color: 'red'}).addTo(map);
                        console.log("Route calculated: " + data.path.length + " points");
                        alert("מסלול נשמר! ID: " + data.route_id);
                    } else {
                        alert("לא נמצא מסלול. בדוק את הכתובות או את השיפוע.");
                    }
                })
                .catch(error => console.error('Error:', error));
            }
        </script>
    </body>
    </html>
    '''

if __name__ == '__main__':
    print("Starting server on 0.0.0.0:8080")
    app.run(debug=True, host='0.0.0.0', port=8080)