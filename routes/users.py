from flask import Blueprint, request, jsonify
from bson.objectid import ObjectId
from db import db
from werkzeug.security import generate_password_hash, check_password_hash  


users_bp = Blueprint("users", __name__)

@users_bp.route("/user", methods=["POST"])
def add_user():
    data = request.json

    if "name" not in data or "password" not in data:
        return jsonify({"error": "Name and password are required"}), 400

    existing = db.users.find_one({"name": data["name"]})
    if existing:
        return jsonify({"error": "User already exists"}), 409

    user = {
        "name": data["name"],
        "password": generate_password_hash(data["password"]),
        "is_admin": data.get("is_admin", False),
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
    }

    db.users.insert_one(user)
    return jsonify({"msg": "User registered successfully"}), 201

@users_bp.route("/user/<user_id>", methods=["DELETE"])
def delete_user(user_id):
    user = db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        return jsonify({"error": "User not found"}), 404

    # 1. Kullanıcının yorumlarını ve puanlarını oyunlardan temizle
    for rating in user.get("ratings", []):
        db.games.update_one(
            {"_id": ObjectId(rating["game_id"])},
            {"$pull": {"ratings": {"user_id": user_id}}}
        )

    for comment in user.get("comments", []):
        db.games.update_one(
            {"_id": ObjectId(comment["game_id"])},
            {"$pull": {"comments": {"user_id": user_id}}}
        )

    # 2. Oyunlardan bu kullanıcının oynama süresini düşür (isteğe bağlı)
    for rating in user.get("ratings", []):
        db.games.update_one(
            {"_id": ObjectId(rating["game_id"])},
            {"$inc": {"play_time": -rating.get("play_time", 0)}}
        )

    # 3. Kullanıcıyı sil
    db.users.delete_one({"_id": ObjectId(user_id)})

    return jsonify({"msg": "User deleted"}), 200
@users_bp.route("/user/<user_id>", methods=["GET"])
def get_user(user_id):
    from bson.objectid import ObjectId

    user = db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        return jsonify({"error": "User not found"}), 404

    # Ortalama puan
    ratings = user.get("ratings", [])
    rated = [r for r in ratings if "rating" in r]
    avg_rating = round(
        sum([r["rating"] for r in rated]) / len(rated), 2
    ) if rated else 0

    # En çok oynanan oyun
    most_played_game_id = None
    max_play_time = -1
    for r in ratings:
        if r.get("play_time", 0) > max_play_time:
            max_play_time = r.get("play_time", 0)
            most_played_game_id = r["game_id"]

    most_played_game = None
    if most_played_game_id:
        game = db.games.find_one({"_id": ObjectId(most_played_game_id)})
        if game:
            most_played_game = game["name"]

    # Yorumlar
    comments_data = []
    for c in sorted(user.get("comments", []), key=lambda x: -x.get("play_time", 0)):
        game = db.games.find_one({"_id": ObjectId(c["game_id"])})
        if game:
            comments_data.append({
                "game_name": game["name"],
                "comment": c["comment"],
                "play_time": c.get("play_time", 0)
            })

    # Son oynanan oyunlar
    recent_out = []
    for r in user.get("recently_played", []):
        game = db.games.find_one({"_id": ObjectId(r["game_id"])})
        if game:
            recent_out.append({
                "game_name": game["name"],
                "played_at": r["timestamp"]
            })

    # İstatistikler
    total_play_time = user.get("play_time", 0)
    games_played = user.get("stats", {}).get("games_played", 1)
    avg_session_time = round(total_play_time / games_played, 1) if games_played > 0 else 0
    comments_made = user.get("stats", {}).get("comments_made", 0)

    return jsonify({
        "name": user["name"],
        "total_play_time": total_play_time,
        "average_rating": avg_rating,
        "most_played_game": most_played_game,
        "comments": comments_data,
        "recently_played": recent_out,
        "stats": {
            "games_played": games_played,
            "avg_session_time": avg_session_time,
            "comments_made": comments_made
        }
    }), 200


@users_bp.route("/user/<user_id>/play", methods=["POST"])
def play_game(user_id):
    data = request.json
    game_id = data.get("game_id")
    duration = data.get("duration", 0)

    if not game_id or duration <= 0:
        return jsonify({"error": "Invalid input"}), 400

    user = db.users.find_one({"_id": ObjectId(user_id)})
    game = db.games.find_one({"_id": ObjectId(game_id)})
    if not user or not game:
        return jsonify({"error": "User or game not found"}), 404

    # Kullanıcıya toplam süre ekle
    db.users.update_one(
        {"_id": ObjectId(user_id)},
        {
            "$inc": {"play_time": duration},
            "$push": {"ratings": {"game_id": game_id, "play_time": duration}},
        }
    )

    # Oyuna toplam süre ekle
    db.games.update_one(
        {"_id": ObjectId(game_id)},
        {"$inc": {"play_time": duration}}
    )

    return jsonify({"msg": f"{duration} minutes added to user and game"}), 200
    # Oyun daha önce oynanmış mı kontrol et (games_played için)
    previously_played = any(r["game_id"] == game_id for r in user.get("ratings", []))
    db.users.update_one(
        {"_id": ObjectId(user_id)},
        {
            "$inc": {
                "play_time": duration,
                "stats.avg_session_time": duration
            },
            "$push": {"ratings": {"game_id": game_id, "play_time": duration}},
        }
    )

    # İlk kez oynuyorsa games_played += 1
    if not previously_played:
        db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$inc": {"stats.games_played": 1}}
        )

@users_bp.route("/user/<user_id>/rate", methods=["POST"])
def rate_game(user_id):
    data = request.json
    game_id = data.get("game_id")
    rating = data.get("rating")

    if not game_id or not (1 <= rating <= 5):
        return jsonify({"error": "Invalid input"}), 400

    user = db.users.find_one({"_id": ObjectId(user_id)})
    game = db.games.find_one({"_id": ObjectId(game_id)})
    if not user or not game:
        return jsonify({"error": "User or game not found"}), 404

    # En az 60 dk oynamış mı?
    played = False
    for r in user.get("ratings", []):
        if r["game_id"] == game_id and r.get("play_time", 0) >= 60:
            played = True
            break

    if not played:
        return jsonify({"error": "Must play at least 1 hour before rating"}), 400

    # Rating güncelle
    db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"ratings.$[elem].rating": rating}},
        array_filters=[{"elem.game_id": game_id}]
    )

    db.games.update_one(
        {"_id": ObjectId(game_id)},
        {"$pull": {"ratings": {"user_id": user_id}}}
    )

    db.games.update_one(
        {"_id": ObjectId(game_id)},
        {"$push": {"ratings": {"user_id": user_id, "rating": rating, "play_time": r["play_time"]}}}
    )

    return jsonify({"msg": "Rating submitted"}), 200
@users_bp.route("/user/<user_id>/comment", methods=["POST"])
def comment_game(user_id):
    data = request.json
    game_id = data.get("game_id")
    comment_text = data.get("comment")

    if not game_id or not comment_text:
        return jsonify({"error": "Invalid input"}), 400

    user = db.users.find_one({"_id": ObjectId(user_id)})
    game = db.games.find_one({"_id": ObjectId(game_id)})
    if not user or not game:
        return jsonify({"error": "User or game not found"}), 404

    # Oynama süresi kontrolü
    play_time = None
    for r in user.get("ratings", []):
        if r["game_id"] == game_id and r.get("play_time", 0) >= 60:
            play_time = r.get("play_time")
            break

    if not play_time:
        return jsonify({"error": "Must play at least 1 hour before commenting"}), 400

    # Puan verip vermediğini kontrol et
    has_rated = any(r.get("game_id") == game_id and "rating" in r for r in user.get("ratings", []))
    if not has_rated:
        return jsonify({"error": "You must rate the game before commenting"}), 400

    # User'a ekle
    db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$push": {"comments": {"game_id": game_id, "comment": comment_text, "play_time": play_time}}}
    )

    # Game'e ekle
    db.games.update_one(
        {"_id": ObjectId(game_id)},
        {"$push": {"comments": {"user_id": user_id, "comment": comment_text, "play_time": play_time}}}
    )

    return jsonify({"msg": "Comment added"}), 200
    # ... yorum işlemi sonrası
    db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$inc": {"stats.comments_made": 1}}
    )


@users_bp.route("/user/<user_id>/favorite", methods=["POST"])
def add_favorite(user_id):
    data = request.json
    game_id = data.get("game_id")

    if not game_id:
        return jsonify({"error": "Missing game_id"}), 400

    user = db.users.find_one({"_id": ObjectId(user_id)})
    game = db.games.find_one({"_id": ObjectId(game_id)})

    if not user or not game:
        return jsonify({"error": "User or game not found"}), 404

    if game_id in user.get("favorites", []):
        return jsonify({"msg": "Game already in favorites"}), 200

    db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$push": {"favorites": game_id}}
    )

    return jsonify({"msg": "Game added to favorites"}), 200
@users_bp.route("/user/<user_id>/favorites", methods=["GET"])
def get_favorites(user_id):
    user = db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        return jsonify({"error": "User not found"}), 404

    favorite_games = []
    for gid in user.get("favorites", []):
        game = db.games.find_one({"_id": ObjectId(gid)})
        if game:
            favorite_games.append({
                "game_id": str(game["_id"]),
                "name": game["name"],
                "photo": game.get("photo"),
                "genres": game.get("genres", [])
            })

    return jsonify(favorite_games), 200


@users_bp.route("/user/login", methods=["POST"])
def login_user():
    data = request.json
    name = data.get("name")
    password = data.get("password")

    if not name or not password:
        return jsonify({"error": "Name and password required"}), 400

    user = db.users.find_one({"name": name})
    if not user or not check_password_hash(user["password"], password):
        return jsonify({"error": "Invalid credentials"}), 401

    return jsonify({
        "msg": "Login successful",
        "user_id": str(user["_id"]),
        "is_admin": user.get("is_admin", False)
    }), 200
@users_bp.route("/all-users", methods=["GET"])
def all_users():
    users = list(db.users.find({}, {"name": 1}))  # Sadece name ve _id alanını alıyoruz
    for u in users:
        u["_id"] = str(u["_id"])  # ObjectId'yi string yap
    return jsonify(users), 200
@users_bp.route("/users", methods=["GET"])
def get_all_users():
    users = list(db.users.find())
    for u in users:
        u["_id"] = str(u["_id"])
    return jsonify(users), 200

