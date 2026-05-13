from flask import Flask, request, jsonify, session, send_from_directory
from pymongo import MongoClient
from bson import ObjectId
import hashlib
import datetime

# ════════════════════════════════════════
#  FLASK APP SETUP
# ════════════════════════════════════════

app = Flask(__name__, static_folder=".", static_url_path="")
app.secret_key = "mentor-connect-secret-2024"

# ════════════════════════════════════════
#  DATABASE CONNECTION  ← THIS IS WHERE
#  YOU CONNECT TO MONGODB
# ════════════════════════════════════════

client = MongoClient("mongodb://localhost:27017/")   # connects to MongoDB
db     = client["mentor_connect"]                    # selects the database

# Collections (like tables in SQL)
users_col    = db["users"]       # stores all users (mentors + mentees)
sessions_col = db["sessions"]    # stores booked sessions
reviews_col  = db["reviews"]     # stores mentor reviews

# ════════════════════════════════════════
#  HELPER FUNCTIONS
# ════════════════════════════════════════

def hash_pw(password):
    """Converts plain password to a secure hash before storing."""
    return hashlib.sha256(password.encode()).hexdigest()

def is_logged_in():
    """Returns True if a user is currently logged in."""
    return "user_id" in session

# ════════════════════════════════════════
#  SERVE FRONTEND
# ════════════════════════════════════════

@app.route("/")
def index():
    """Serves the main HTML file."""
    return send_from_directory(".", "index.html")

# ════════════════════════════════════════
#  AUTH ROUTES
# ════════════════════════════════════════

@app.route("/register", methods=["POST"])
def register():
    """
    Creates a new user account.
    Receives: name, email, password, role, skills (list), bio
    Saves to: users_col (MongoDB)
    """
    data     = request.get_json()
    name     = data.get("name", "").strip()
    email    = data.get("email", "").strip().lower()
    password = data.get("password", "")
    role     = data.get("role", "mentee")        # "mentor" or "mentee"
    skills   = data.get("skills", [])            # list of skill strings
    bio      = data.get("bio", "").strip()

    # Validation
    if not name or not email or not password:
        return jsonify({"error": "Please fill in all fields."}), 400

    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters."}), 400

    # Check if email already exists in MongoDB
    if users_col.find_one({"email": email}):
        return jsonify({"error": "This email is already registered."}), 409

    # Build the user document and insert into MongoDB
    user = {
        "name":         name,
        "email":        email,
        "password":     hash_pw(password),   # never store plain passwords!
        "role":         role,
        "skills":       skills,
        "bio":          bio,
        "rating":       0.0,
        "review_count": 0,
        "created_at":   datetime.datetime.utcnow()
    }
    result = users_col.insert_one(user)   # ← SAVES TO MONGODB

    # Store user info in Flask session (keeps user logged in)
    session["user_id"] = str(result.inserted_id)
    session["name"]    = name
    session["role"]    = role

    return jsonify({"message": f"Welcome, {name}! Your account is ready.", "name": name, "role": role}), 201


@app.route("/login", methods=["POST"])
def login():
    """
    Logs in an existing user.
    Checks email + hashed password against MongoDB.
    """
    data     = request.get_json()
    email    = data.get("email", "").strip().lower()
    password = data.get("password", "")

    # Look up user in MongoDB
    user = users_col.find_one({"email": email, "password": hash_pw(password)})  # ← READS FROM MONGODB

    if not user:
        return jsonify({"error": "Wrong email or password. Please try again."}), 401

    # Save to session
    session["user_id"] = str(user["_id"])
    session["name"]    = user["name"]
    session["role"]    = user["role"]

    return jsonify({"message": f"Welcome back, {user['name']}!", "name": user["name"], "role": user["role"]}), 200


@app.route("/logout")
def logout():
    """Clears the session — logs the user out."""
    session.clear()
    return jsonify({"message": "You have been logged out."}), 200


@app.route("/me")
def me():
    """
    Returns info about the currently logged-in user.
    Used by the frontend to check if user is logged in.
    """
    if not is_logged_in():
        return jsonify({"error": "Not logged in."}), 401

    # Fetch fresh data from MongoDB
    user = users_col.find_one({"_id": ObjectId(session["user_id"])}, {"password": 0})  # ← READS FROM MONGODB

    if not user:
        session.clear()
        return jsonify({"error": "User not found."}), 404

    return jsonify({
        "id":           str(user["_id"]),
        "name":         user["name"],
        "email":        user["email"],
        "role":         user["role"],
        "skills":       user.get("skills", []),
        "bio":          user.get("bio", ""),
        "rating":       user.get("rating", 0.0),
        "review_count": user.get("review_count", 0)
    }), 200

# ════════════════════════════════════════
#  MENTOR ROUTES
# ════════════════════════════════════════

@app.route("/mentors")
def get_mentors():
    """
    Returns a list of all mentors.
    Optional ?q=keyword to search by name, skill, or bio.
    Reads from: users_col (MongoDB)
    """
    q     = request.args.get("q", "").strip()
    query = {"role": "mentor"}   # only fetch users who are mentors

    # If search keyword provided, search across name, skills, and bio
    if q:
        query["$or"] = [
            {"name":   {"$regex": q, "$options": "i"}},
            {"skills": {"$regex": q, "$options": "i"}},
            {"bio":    {"$regex": q, "$options": "i"}}
        ]

    # Fetch from MongoDB (exclude password field)
    mentors = list(users_col.find(query, {"password": 0}))   # ← READS FROM MONGODB

    result = []
    for m in mentors:
        result.append({
            "id":           str(m["_id"]),
            "name":         m["name"],
            "skills":       m.get("skills", []),
            "bio":          m.get("bio", "No bio yet."),
            "rating":       round(m.get("rating", 0.0), 1),
            "review_count": m.get("review_count", 0)
        })

    return jsonify(result), 200

# ════════════════════════════════════════
#  SESSION / BOOKING ROUTES
# ════════════════════════════════════════

@app.route("/book", methods=["POST"])
def book():
    """
    Books a session between a mentee and a mentor.
    Checks for time slot clashes before saving.
    Saves to: sessions_col (MongoDB)
    """
    if not is_logged_in():
        return jsonify({"error": "Please log in first to book a session."}), 401

    data      = request.get_json()
    mentor_id = data.get("mentor_id", "")
    date_str  = data.get("date", "")      # format: "2025-06-15"
    time_str  = data.get("time", "")      # format: "14:00"
    topic     = data.get("topic", "").strip()

    # Basic validation
    if not mentor_id or not date_str or not time_str:
        return jsonify({"error": "Please provide mentor, date, and time."}), 400

    # Check mentor exists in MongoDB
    try:
        mentor = users_col.find_one({"_id": ObjectId(mentor_id), "role": "mentor"})  # ← READS FROM MONGODB
    except Exception:
        return jsonify({"error": "Invalid mentor ID."}), 400

    if not mentor:
        return jsonify({"error": "Mentor not found."}), 404

    # Parse the date and time into a datetime object
    try:
        scheduled_at = datetime.datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    except ValueError:
        return jsonify({"error": "Invalid date or time format."}), 400

    # Check if this time slot is already booked for the mentor
    clash = sessions_col.find_one({   # ← READS FROM MONGODB
        "mentor_id":    mentor_id,
        "scheduled_at": scheduled_at,
        "status":       {"$ne": "cancelled"}   # ignore cancelled sessions
    })
    if clash:
        return jsonify({"error": "This time slot is already taken. Please choose another."}), 409

    # Save the session to MongoDB
    sessions_col.insert_one({   # ← SAVES TO MONGODB
        "mentee_id":    session["user_id"],
        "mentee_name":  session["name"],
        "mentor_id":    mentor_id,
        "mentor_name":  mentor["name"],
        "topic":        topic or "General Session",
        "scheduled_at": scheduled_at,
        "status":       "upcoming",
        "created_at":   datetime.datetime.utcnow()
    })

    return jsonify({
        "message": f"Session booked with {mentor['name']} on {date_str} at {time_str}! 🎉"
    }), 201


@app.route("/my-sessions")
def my_sessions():
    """
    Returns all sessions for the currently logged-in user.
    Mentees see sessions they booked; mentors see sessions booked with them.
    Reads from: sessions_col (MongoDB)
    """
    if not is_logged_in():
        return jsonify({"error": "Please log in to view your sessions."}), 401

    user_id = session["user_id"]
    role    = session["role"]

    # Build query based on role
    query = {"mentee_id": user_id} if role == "mentee" else {"mentor_id": user_id}

    # Fetch sessions from MongoDB, sorted by date (soonest first)
    raw_sessions = list(sessions_col.find(query).sort("scheduled_at", 1))   # ← READS FROM MONGODB

    result = []
    for s in raw_sessions:
        result.append({
            "id":           str(s["_id"]),
            "mentor_name":  s.get("mentor_name", ""),
            "mentee_name":  s.get("mentee_name", ""),
            "topic":        s.get("topic", "General Session"),
            "scheduled_at": s["scheduled_at"].strftime("%d %b %Y at %I:%M %p"),
            "status":       s.get("status", "upcoming")
        })

    return jsonify(result), 200


@app.route("/cancel-session/<session_id>", methods=["POST"])
def cancel_session(session_id):
    """
    Cancels a session by setting its status to 'cancelled'.
    Only the mentor or mentee involved can cancel.
    Updates: sessions_col (MongoDB)
    """
    if not is_logged_in():
        return jsonify({"error": "Please log in."}), 401

    try:
        sess = sessions_col.find_one({"_id": ObjectId(session_id)})   # ← READS FROM MONGODB
    except Exception:
        return jsonify({"error": "Invalid session ID."}), 400

    if not sess:
        return jsonify({"error": "Session not found."}), 404

    # Make sure only the people involved can cancel
    user_id = session["user_id"]
    if sess["mentee_id"] != user_id and sess["mentor_id"] != user_id:
        return jsonify({"error": "You are not part of this session."}), 403

    # Update status to cancelled in MongoDB
    sessions_col.update_one(   # ← UPDATES IN MONGODB
        {"_id": ObjectId(session_id)},
        {"$set": {"status": "cancelled"}}
    )

    return jsonify({"message": "Session cancelled successfully."}), 200


# ════════════════════════════════════════
#  RUN THE APP
# ════════════════════════════════════════

if __name__ == "__main__":
    print("🚀 Mentor Connect is running!")
    print("📦 Connected to MongoDB: mentor_connect database")
    print("🌐 Open your browser at: http://localhost:5000")
    app.run(debug=True)
