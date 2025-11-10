from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import sqlite3, os
from werkzeug.utils import secure_filename

app = Flask(__name__)

CORS(app, resources={r"/*": {"origins": "*"}})
 
# ---------------- DB SETTINGS ----------------
DB_FILE = "main.db"

def get_connection():
    conn = sqlite3.connect(DB_FILE) 
    conn.row_factory = sqlite3.Row
    return conn

def create_tables():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS auth (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT    -- ✅ new column
    );
""")

   


    cur.execute("""
        CREATE TABLE IF NOT EXISTS providers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            name TEXT,
            service TEXT,
            contact TEXT,
            location TEXT,
            experience TEXT,
            availability TEXT,
            rate TEXT,
            photo TEXT,
            status TEXT,    
            FOREIGN KEY(user_id) REFERENCES auth(id)
        );
    """)
    cur.execute(""" CREATE TABLE IF NOT EXISTS reviews (
           id INTEGER PRIMARY KEY AUTOINCREMENT,
           user_id INTEGER,
           username TEXT,     
           rating INTEGER NOT NULL,
           review TEXT NOT NULL,
           created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

    """)
    cur.execute("""CREATE TABLE IF NOT EXISTS complaints (
           id INTEGER PRIMARY KEY AUTOINCREMENT,
           user_id INTEGER,
           provider_id INTEGER,
           complaint TEXT NOT NULL,
           status TEXT DEFAULT 'pending',
           created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
           FOREIGN KEY(user_id) REFERENCES auth(id),
           FOREIGN KEY(provider_id) REFERENCES providers(id)
        );
                
    """)

   
    conn.commit()
    conn.close()

create_tables()
# ✅ Folder to store provider images
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

#  ......................admin account registered.................
def create_admin():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT * FROM auth WHERE role='admin'")
    admin = cur.fetchone()

    if not admin:
        cur.execute("""
            INSERT INTO auth (username, email, password, role)
            VALUES ('admin', 'admin@admin.com', 'admin123', 'admin')
        """)
        conn.commit()
        print("✅ Admin created: username=admin, password=admin123")

    conn.close()

create_admin()
# ✅ Fetch all registered users (Admin only)
@app.route("/admin/get_users", methods=["GET"])
def get_users():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, username, email, role FROM auth")
    users = cur.fetchall()
    conn.close()

    return jsonify({"users": [dict(u) for u in users]})

@app.route("/admin/providers", methods=["GET"])
def get_providers():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM providers")
    data = cur.fetchall()
    conn.close()

    providers = [
        {
            "id": row["id"],
            "name": row["name"],
            "service": row["service"],
            "contact": row["contact"],
            "location": row["location"],
            "availability":row["availability"],
            "experience":row["experience"],
            "rate":row["rate"],
            "status": row["status"],
        }
        for row in data
    ]

    return jsonify({"providers": providers})
@app.route("/api/complaints", methods=["POST"])
def add_complaint():
   try:
        data = request.get_json()
        print("📩 Received complaint data:", data)  # Debug

        if not data:
            return jsonify({"error": "No data received"}), 400

        user_id = data.get("user_id")
        provider_id = data.get("provider_id")
        complaint_text = data.get("complaint")

        # ✅ Validate fields
        if not user_id or not provider_id or not complaint_text:
            print("⚠️ Missing required fields:", data)
            return jsonify({"error": "Missing required fields"}), 400

        conn = sqlite3.connect("main.db")
        cur = conn.cursor()

        cur.execute(
            "INSERT INTO complaints (user_id, provider_id, complaint) VALUES (?, ?, ?)",
            (user_id, provider_id, complaint_text),
        )
        conn.commit()
        conn.close()

        print("✅ Complaint saved successfully.")
        return jsonify({"message": "Complaint saved successfully"}), 200

   except Exception as e:
        print("❌ Error in /api/complaints:", str(e))
        return jsonify({"error": str(e)}), 500
@app.route("/admin/complaints", methods=["GET"])
def get_complaints():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT c.id, a.username AS user_name, p.name AS provider_name,
               c.complaint, c.status, c.created_at
        FROM complaints c
        LEFT JOIN auth a ON c.user_id = a.id
        LEFT JOIN providers p ON c.provider_id = p.id
        ORDER BY c.created_at DESC
    """)
    rows = cur.fetchall()
    conn.close()

    complaints = [dict(row) for row in rows]
    print("🧾 Complaints fetched:", complaints)  #
    return jsonify({"complaints": complaints})

@app.route("/admin/complaints/<int:complaint_id>/resolve", methods=["POST"])
def resolve_complaint(complaint_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE complaints SET status = 'resolved' WHERE id = ?", (complaint_id,))
    conn.commit()
    conn.close()
    return jsonify({"message": "✅ Complaint marked as resolved."})


@app.route("/admin/provider/approve/<int:id>", methods=["POST"])
def approve_provider(id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE providers SET status='approved' WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return jsonify({"message": "Provider Approved ✅"})


@app.route("/admin/provider/reject/<int:id>", methods=["POST"])
def reject_provider(id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE providers SET status='rejected' WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return jsonify({"message": "Provider Rejected ❌"})
@app.route("/admin/get_provider_stats", methods=["GET"])
def get_provider_stats():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM providers")
    total = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM providers WHERE status='pending'")
    pending = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM providers WHERE status='approved'")
    approved = cur.fetchone()[0]

    conn.close()

    return jsonify({
        "total": total,
        "pending": pending,
        "approved": approved
    })

@app.route("/edit_provider/<int:id>", methods=["PUT"])
def edit_provider(id):
    data = request.json

    name = data.get("name")
    service = data.get("service")
    contact = data.get("contact")
    location = data.get("location")
    availability = data.get("availability")
    experience = data.get("experience")
    rate = data.get("rate")



   
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE providers 
        SET name=?, service=?, contact=?, location=?, availability=?, experience=?, rate=?
        WHERE id=?
    """, (name, service, contact, location, availability, experience, rate, id))

    conn.commit()
    conn.close()

    return jsonify({"message": "Provider updated successfully"})

@app.route("/register_provider", methods=["POST"])
def register_provider():
    user_id = request.form.get("user_id")
    name = request.form.get("name")
    service = request.form.get("service")
    contact = request.form.get("contact")
    location = request.form.get("location")
    experience = request.form.get("experience")
    availability = request.form.get("availability")
    rate = request.form.get("rate")

    photo = request.files.get("photo")
    filename = None

    # ✅ Save photo only if uploaded
    if photo:
        filename = f"user_{user_id}.jpg"
        photo.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
    else:
        filename = None

    # ✅ Insert provider data into the database
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO providers 
        (user_id, name, service, contact, location, experience, availability, rate, photo)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (user_id, name, service, contact, location, experience, availability, rate, filename))

    conn.commit()
    conn.close()

    # ✅ Return a success response
    return jsonify({
        "message": "✅ Provider registered successfully!",
        "photo_url": f"https://job-service-backend.onrender.com/uploads/{filename}" if filename else None
    }), 200


# ---------------- Serve Uploaded Images ----------------
@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

# ---------------- SIGNUP ----------------
@app.route("/signup", methods=["POST"])
def signup():
    data = request.get_json()
    username = data.get("username")
    email = data.get("email")
    password = data.get("password")

    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            "INSERT INTO auth (username, email, password) VALUES (?, ?, ?)",
            (username, email, password)
        )
        conn.commit()
        return jsonify({"message": "✅ Account created successfully!"}), 200

    except sqlite3.IntegrityError:
        return jsonify({"message": "❌ Username or Email already exists"}), 400

# ---------------- LOGIN ----------------
@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM auth WHERE username=? AND password=?", (username, password))
    user = cur.fetchone()
    conn.close()

    if user:
        return jsonify({
            "message": "✅ Login successful",
            "user": {
                "id": user["id"],
                "username": user["username"],
                "email": user["email"],
                "role": user["role"]
            }
        }), 200
    else:
        return jsonify({"message": "❌ Invalid username or password"}), 401
    # .......................... register client ......................................


   


# ---------------- REGISTER PROVIDER ----------------
 

@app.route("/update_provider", methods=["PUT"])  
def update_provider():
    user_id = request.form.get("user_id")
    name = request.form.get("name")
    service = request.form.get("service")
    contact = request.form.get("contact")
    location = request.form.get("location")
    experience = request.form.get("experience")
    availability = request.form.get("availability")
    rate = request.form.get("rate")

    old_photo = request.form.get("old_photo")  #  get old photo name
    photo = request.files.get("photo")
    filename = old_photo  # ✅ default to old photo if no new one

    # ✅ if new photo uploaded overwrite old one
    if photo:
        ext = photo.filename.rsplit(".", 1)[-1]
        filename = f"user_{user_id}.{ext}"
        photo.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE providers
        SET name=?, service=?, contact=?, location=?, experience=?, availability=?, rate=?, photo=?
        WHERE user_id=?
    """, (name, service, contact, location, experience, availability, rate, filename, user_id))

    conn.commit()

    cur.execute("SELECT * FROM providers WHERE user_id=?", (user_id,))
    provider = cur.fetchone()
    conn.close()

    provider_dict = dict(provider)

    return jsonify({
        "message": "✅ Provider updated",
        "provider": provider_dict,
        "filename": filename
    })

    


# ---------------- GET PROVIDER ----------------
@app.route('/get_provider/<int:user_id>', methods=['GET'])
def get_provider(user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM providers WHERE user_id=?", (user_id,))
    provider = cur.fetchone()
    conn.close()

    if provider:
        provider_dict = dict(provider)

        if provider_dict.get("photo"):
            provider_dict["photo"] = f"https://job-service-backend.onrender.com/uploads/{provider_dict['photo']}"
            

        return jsonify({"provider": provider_dict})

    return jsonify({"provider": None})
@app.route("/api/providers", methods=["GET"])
def search_providers():
    search = request.args.get("search", "").lower()

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    SELECT 
        id, user_id, name, service, contact, location, experience, availability, rate, photo 
    FROM providers
    WHERE (lower(service) LIKE ?
        OR lower(location) LIKE ?
        OR lower(name) LIKE ?)
        AND status='approved'
""", (f"%{search}%", f"%{search}%", f"%{search}%"))


    rows = cur.fetchall()
    conn.close()

    providers = []
    for row in rows:
        provider = dict(row)
        if provider.get("photo"):
            provider["photo"] = f"https://job-service-backend.onrender.com/uploads/{provider['photo']}"
        providers.append(provider)

    return jsonify(providers)
@app.route("/delete_account/<int:user_id>", methods=["DELETE"])
def delete_account(user_id):
    try:
        conn = get_connection()
        cur = conn.cursor()

        # ✅ Delete provider record first
        cur.execute("DELETE FROM providers WHERE user_id=?", (user_id,))

        # ✅ Remove provider profile photo if exists
        photo_path = os.path.join(app.config["UPLOAD_FOLDER"], f"user_{user_id}.jpg")
        if os.path.exists(photo_path):
            os.remove(photo_path)

        # ✅ Delete user
        cur.execute("DELETE FROM auth WHERE id=?", (user_id,))
 
        conn.commit() 
        conn.close()

        return jsonify({"message": "✅ Account deleted successfully"}), 200

    except Exception as e:
        print(e)
        return jsonify({"message": "❌ Error deleting account"}), 500

@app.route("/delete_provider/<int:id>", methods=["DELETE"])
def delete_provider(id):
    conn = get_connection()
    cursor = conn.cursor()

    # ✅ Get provider info to find user_id
    cursor.execute("SELECT user_id FROM providers WHERE id = ?", (id,))
    provider = cursor.fetchone()

    if not provider:
        conn.close()
        return jsonify({"message": "❌ Provider not found"}), 404

    user_id = provider["user_id"]

    # ✅ Delete provider entry
    cursor.execute("DELETE FROM providers WHERE id = ?", (id,))

    # ✅ Delete associated user account from auth
    cursor.execute("DELETE FROM auth WHERE id = ?", (user_id,))

    # ✅ Delete provider’s photo if exists
    photo_path = os.path.join(app.config["UPLOAD_FOLDER"], f"user_{user_id}.jpg")
    if os.path.exists(photo_path):
        os.remove(photo_path)

    conn.commit()
    conn.close()

    return jsonify({"message": "✅ Provider and account deleted successfully"}), 200

# 
@app.route("/api/reviews", methods=["POST"])
def add_review():
    data = request.get_json()
    user_id = data["userId"]   # ✅ Get userId
    username = data["username"]
    rating = data["rating"]
    review = data["review"]

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO reviews (user_id, username, rating, review, created_at) VALUES (?, ?, ?, ?, datetime('now'))",
        (user_id, username, rating, review)   # ✅ Save user_id too
    )

    conn.commit()
    conn.close()

    return jsonify({"message": "Review added"}), 201

@app.route("/set_role", methods=["POST"])
def set_role():
    data = request.get_json()
    user_id = data.get("user_id")
    role = data.get("role")

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE auth SET role=? WHERE id=?", (role, user_id))
    conn.commit()
    conn.close()

    return jsonify({"message": "Role updated"})
   


@app.route("/api/reviews", methods=["GET"])
def get_reviews():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT r.username, r.rating, r.review, r.created_at 
        FROM reviews r
        JOIN (
            SELECT user_id, MAX(id) AS latest_id
            FROM reviews
            GROUP BY user_id
        ) latest
        ON r.id = latest.latest_id
        ORDER BY r.created_at DESC
    """)

    rows = cursor.fetchall()
    conn.close()

    reviews = []
    for row in rows:
        reviews.append({
            "username": row["username"],
            "rating": row["rating"],
            "review": row["review"],
            "created_at": row["created_at"]
        })
    print("Reviews from DB:", rows)

    return jsonify(reviews), 200

@app.route("/")
def home():
    return jsonify({"message": "Backend is running ✅"})
@app.route("/admin/reviews", methods=["GET"])
def admin_reviews():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT 
            r.id, 
            a.username AS user_name,
            r.rating, 
            r.review, 
            r.created_at
        FROM reviews r
        LEFT JOIN auth a ON r.user_id = a.id
        ORDER BY r.created_at DESC
    """)

    rows = cur.fetchall()
    conn.close()

    reviews = [dict(row) for row in rows]
    print("🧾 Admin fetched reviews:", reviews)
    return jsonify({"reviews": reviews}), 200



# ---------------- RUN SERVER ----------------
if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)

