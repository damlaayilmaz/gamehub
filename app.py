# app.py
from flask import Flask, render_template
from routes.games import games_bp
from routes.users import users_bp
from flask_cors import CORS
from werkzeug.security import generate_password_hash
from db import db
import os

def create_app():
    app = Flask(
        __name__,
        template_folder="frontend",
        static_folder="frontend",
        static_url_path=""
    )
    CORS(app)
    app.register_blueprint(games_bp)
    app.register_blueprint(users_bp)

    @app.route("/")
    def index():
        return render_template("index.html")

    # frontend içindeki tüm html dosyaları otomatik route
    html_files = [f for f in os.listdir("frontend") if f.endswith(".html")]
    for filename in html_files:
        route_path = "/" + filename
        template_name = filename

        def make_view(template_name):
            def view():
                return render_template(template_name)
            return view

        endpoint_name = filename.replace(".", "_")
        app.add_url_rule(route_path, endpoint=endpoint_name, view_func=make_view(template_name))

    # Admin kullanıcı otomatik oluşturma
    admin_name = "admin"
    admin_password = "admin123"
    if not db.users.find_one({"name": admin_name, "is_admin": True}):
        db.users.insert_one({
            "name": admin_name,
            "password": generate_password_hash(admin_password),
            "is_admin": True,
            "play_time": 0,
            "ratings": [],
            "comments": [],
            "favorites": [],
            "stats": {
                "games_played": 0,
                "avg_session_time": 0,
                "comments_made": 0
            },
            "recently_played": []
        })
        print(f"✅ Admin user created: {admin_name} / {admin_password}")
    else:
        print("ℹ️ Admin user already exists.")

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
