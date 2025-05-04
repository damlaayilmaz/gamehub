from flask import Blueprint, request, jsonify
from bson.objectid import ObjectId
from db import db

games_bp = Blueprint("games", __name__)

@games_bp.route("/game", methods=["POST"])
def add_game():
    user_id = request.args.get("user_id")
    user = db.users.find_one({"_id": ObjectId(user_id)})

    if not user or not user.get("is_admin", False):
        return jsonify({"error": "Only admins can add games"}), 403

    data = request.json

    required = ["name", "genres", "photo"]
    if not all(k in data for k in required):
        return jsonify({"error": "Missing required fields"}), 400

    game = {
        "name": data["name"],
        "genres": data["genres"],
        "photo": data["photo"],
        "description": data.get("description", ""),
        "tags": data.get("tags", []),
        "optional_fields": data.get("optional_fields", {}),
        "play_time": 0,
        "ratings": [],
        "comments": [],
        "is_comment_enabled": True,
        "ratings_enabled": True
    }

    db.games.insert_one(game)
    return jsonify({"msg": "Game added"}), 201

@games_bp.route("/game/<game_id>", methods=["DELETE"])
def delete_game(game_id):
    user_id = request.args.get("user_id")
    user = db.users.find_one({"_id": ObjectId(user_id)})

    if not user or not user.get("is_admin", False):
        return jsonify({"error": "Only admins can delete games"}), 403

    result = db.games.delete_one({"_id": ObjectId(game_id)})
    if result.deleted_count == 0:
        return jsonify({"error": "Game not found"}), 404
    return jsonify({"msg": "Game deleted"}), 200

@games_bp.route("/game/<game_id>/toggle-comments", methods=["PATCH"])
def toggle_comments(game_id):
    game = db.games.find_one({"_id": ObjectId(game_id)})
    if not game:
        return jsonify({"error": "Game not found"}), 404

    new_state = not game.get("is_comment_enabled", True)

    db.games.update_one(
        {"_id": ObjectId(game_id)},
        {"$set": {"is_comment_enabled": new_state}}
    )

    return jsonify({
        "msg": "Comment toggled",
        "new_state": new_state
    }), 200

@games_bp.route("/game/<game_id>/toggle-ratings", methods=["PATCH"])
def toggle_ratings(game_id):
    game = db.games.find_one({"_id": ObjectId(game_id)})
    if not game:
        return jsonify({"error": "Game not found"}), 404

    new_state = not game.get("ratings_enabled", True)

    db.games.update_one(
        {"_id": ObjectId(game_id)},
        {"$set": {"ratings_enabled": new_state}}
    )

    return jsonify({
        "msg": "Rating toggled",
        "new_state": new_state
    }), 200

@games_bp.route("/games", methods=["GET"])
def get_games():
    tag_filter = request.args.get("tag")
    query = {"tags": tag_filter} if tag_filter else {}

    games = list(db.games.find(query))
    for game in games:
        game["_id"] = str(game["_id"])
    return jsonify(games), 200

@games_bp.route("/game/<game_id>", methods=["GET"])
def get_game(game_id):
    game = db.games.find_one({"_id": ObjectId(game_id)})
    if not game:
        return jsonify({"error": "Game not found"}), 404

    # Ortalama puan hesapla
    ratings = game.get("ratings", [])
    avg_rating = (
        sum([r["rating"] for r in ratings]) / len(ratings)
        if ratings else 0
    )

    # Yorumları topla (isimle birlikte)
    comments_out = []
    for c in game.get("comments", []):
        user = db.users.find_one({"_id": ObjectId(c["user_id"])})
        if user:
            comments_out.append({
                "user_name": user["name"],
                "comment": c["comment"],
                "play_time": c.get("play_time", 0)
            })

    return jsonify({
        "name": game["name"],
        "genres": game["genres"],
        "average_rating": round(avg_rating, 2),
        "total_play_time": game.get("play_time", 0),
        "comments": comments_out,
        "is_comment_enabled": game.get("is_comment_enabled", True),
        "ratings_enabled": game.get("ratings_enabled", True)
    }), 200

