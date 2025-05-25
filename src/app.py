import os
from flask import Flask, send_from_directory, request, jsonify
from flask_cors import CORS
import work_calculate_ways.pathFinding as pathFinding
import json
from routes.api_routes import api_bp
from routes.map_routes import map_bp
import city

app = Flask(__name__)
CORS(app)

DIST_DIR = "/Users/yuval/clientBikers/dist"


# ראוטים שמגישים את index.html של React לכל מי שנכנס דרך הדפדפן
@app.route('/register')
@app.route('/login')
def serve_react_app():
    return send_from_directory(DIST_DIR, 'index.html')


# ראוט שמטפל בקבצים הסטטיים של React (JS, CSS וכו')
@app.route('/_expo/<path:path>')
def serve_expo_assets(path):
    return send_from_directory(os.path.join(DIST_DIR, '_expo'), path)

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
        <title>מפת מסלול רוכבים</title>
        <link rel="icon" type="image/x-icon" href="/favicon.ico">
        <link href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" rel="stylesheet"/>
        <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
        <style>
            body, html {
                margin: 0;
                padding: 0;
                height: 100%;
                direction: rtl;
                font-family: Arial, sans-serif;
            }
            #container {
                display: flex;
                height: 100vh;
                width: 100vw;
            }
            #form-panel {
                width: 350px;
                padding: 20px;
                background-color: #f5f5f5;
                box-shadow: 0 0 10px rgba(0,0,0,0.2);
                box-sizing: border-box;
                overflow-y: auto;
            }
            label {
                display: block;
                margin-top: 15px;
            }
            input {
                width: 100%;
                padding: 8px;
                margin-top: 5px;
                box-sizing: border-box;
            }
            button {
                margin-top: 20px;
                padding: 10px;
                width: 100%;
                font-size: 16px;
                cursor: pointer;
            }
            #osm-map {
                flex-grow: 1;
                height: 100%;
                width: 100%;
            }
        </style>
    </head>
    <body>
        <div id="container">
            <div id="form-panel">
                <h2>מסלול מותאם</h2>
                <label for="email">אימייל:</label>
                <input type="email" id="email" placeholder="הזן אימייל">

                <label for="start-point">נקודת התחלה:</label>
                <input type="text" id="start-point" autocomplete = "on" placeholder="רחוב, עיר">
                
                <label for="end-point">נקודת סיום:</label>
                <input type="text" id="end-point" autocomplete = "on" placeholder="רחוב, עיר">

                <label for="max-slope">שיפוע מרבי (0-270 מעלות):</label>
                <input type="number" id="max-slope" min="0" max="270" value="90">

                <button onclick="calculateRoute()">חפש מסלול</button>

                <button onclick="window.location.href='/register'">הרשמה</button>
                <button onclick="window.location.href='/login'" style="margin-top: 10px;">התחברות</button>
            </div>

            <div id="osm-map"></div>
        </div>

        <script>
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
                        map.eachLayer(layer => {
                            if (layer instanceof L.Polyline) map.removeLayer(layer);
                        });
                        var pathCoords = data.path.map(coord => [coord.latitude, coord.longitude]);
                        L.polyline(pathCoords, {color: 'red'}).addTo(map);
                        map.fitBounds(pathCoords);
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