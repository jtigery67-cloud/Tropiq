import os
from flask import Flask, render_template, request, redirect, session, send_from_directory
from werkzeug.utils import secure_filename
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_socketio import SocketIO, emit
import os

app = Flask(__name__, instance_path=os.path.join(os.getcwd(), "instance"))

app.config["SECRET_KEY"] = "secret123"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///app.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

socketio = SocketIO(app, cors_allowed_origins="*")

db = SQLAlchemy(app)

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///app.db"

# ---------------- USERS ----------------
users = {
    "admin": "1234"
}

# ---------------- DATABASE MODEL ----------------
class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50))
    content = db.Column(db.String(300))
    image = db.Column(db.String(200))
    video = db.Column(db.String(200), default="")
    likes = db.Column(db.Integer, default=0)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    comments = db.relationship("Comment", backref="post", cascade="all, delete")
class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey("post.id"))
    text = db.Column(db.String(300))
    username = db.Column(db.String(50))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(
        db.String(50),
        unique=True,
        nullable=False
    )

    password = db.Column(
        db.String(100),
        nullable=False
    )

    profile_pic = db.Column(
        db.String(200),
        default=""
    )

    bio = db.Column(
    db.String(300),
    default=""
    )

class Follow(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    follower_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id")
    )

    following_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id")
    )

class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    post_id = db.Column(db.Integer, db.ForeignKey("post.id"))

# ---------------- HOME ----------------

@app.route("/")
def home():

    if "user" not in session:
        return redirect("/login")

    current_user = User.query.filter_by(
        username=session["user"]
    ).first()

    if current_user is None:
        session.clear()
        return redirect("/login")

    posts = Post.query.order_by(Post.id.desc()).all()

    liked_posts = Like.query.filter_by(
        user_id=current_user.id
    ).all()

    liked_post_ids = [like.post_id for like in liked_posts]

    return render_template(
        "home.html",
        posts=posts,
        liked_post_ids=liked_post_ids
    )
@app.route("/profile/<username>")
def profile(username):

    user = User.query.filter_by(username=username).first()

    user_posts = Post.query.filter_by(username=username)\
                           .order_by(Post.id.desc())\
                           .all()

    followers = ...
    following = ...
    is_following = ...

    # ✅ ADD THIS BLOCK
    current_user = User.query.filter_by(
        username=session["user"]
    ).first()

    liked_posts = Like.query.filter_by(
        user_id=current_user.id
    ).all()

    liked_post_ids = [like.post_id for like in liked_posts]

    return render_template(
        "profile.html",
        username=username,
        user=user,
        posts=user_posts,
        followers=followers,
        following=following,
        is_following=is_following,
        liked_post_ids=liked_post_ids
    )

# ---------------- POST ----------------
@app.route("/post", methods=["POST"])
def post():

    if "user" not in session:
        return redirect("/login")

    username = session.get("user")
    content = request.form["content"]

    image = request.files.get("image")
    filename = ""

    if image and image.filename:
        filename = secure_filename(image.filename)
        image.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

    new_post = Post(
        username=username,
        content=content,
        image=filename
    )

    db.session.add(new_post)
    db.session.commit()

    socketio.emit("new_post", {
        "username": username,
        "content": content,
        "image": filename
    })

    return redirect("/")
# ---------------- LIKE ----------------
@app.route("/like/<int:post_id>")
def like(post_id):

    if "user" not in session:
        return redirect("/login")

    user = User.query.filter_by(username=session["user"]).first()
    post = Post.query.get(post_id)

    if not post:
        return redirect("/")

    existing_like = Like.query.filter_by(
        user_id=user.id,
        post_id=post_id
    ).first()

    liked = False

    if existing_like:
        db.session.delete(existing_like)
        if post.likes > 0:
            post.likes -= 1
        liked = False
    else:
        new_like = Like(user_id=user.id, post_id=post_id)
        db.session.add(new_like)
        post.likes += 1
        liked = True

    db.session.commit()

    # 🔥 REAL-TIME BROADCAST
    socketio.emit("like_update", {
        "post_id": post_id,
        "likes": post.likes,
        "liked": liked
    })

    return "", 204
# ---------------- COMMENTS (TEMP SIMPLE VERSION) ----------------
@app.route("/comment/<int:post_id>", methods=["POST"])
def comment(post_id):

    text = request.form["comment"]
    username = session.get("user")

    new_comment = Comment(
        post_id=post_id,
        text=text,
        username=username
    )

    db.session.add(new_comment)
    db.session.commit()

    return redirect("/")

# ---------------- UPLOADS ----------------
@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

# ---------------- LOGIN ----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        user = User.query.filter_by(username=username).first()
        print(user)
        if user and check_password_hash(user.password, password):
            session["user"] = user.username
            return redirect("/")

        return "Invalid username or password"

    return render_template("login.html")

# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect("/login")

# ---------------- INIT DB ----------------
with app.app_context():
    db.create_all()

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        existing_user = User.query.filter_by(username=username).first()

        if existing_user:
            return "Username already exists"

        new_user = User(
            username=username,
            password=generate_password_hash(password)
        )

        db.session.add(new_user)
        db.session.commit()

        return redirect("/login")

    return render_template("register.html")

@app.route("/upload_profile_pic", methods=["POST"])
def upload_profile_pic():

    if "user" not in session:
        return redirect("/login")

    image = request.files.get("profile_pic")

    if image and image.filename:

        filename = secure_filename(image.filename)

        print("UPLOAD FOLDER:", app.config["UPLOAD_FOLDER"])

        save_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        image.save(save_path)

        print("SAVED TO:", save_path)

        user = User.query.filter_by(username=session["user"]).first()
        user.profile_pic = filename

        db.session.commit()

    else:
        print("NO FILE RECEIVED")

    return redirect(f"/profile/{session['user']}")

@app.route("/edit_profile", methods=["GET", "POST"])
def edit_profile():

    if "user" not in session:
        return redirect("/login")

    user = User.query.filter_by(username=session["user"]).first()

    if request.method == "POST":

        new_username = request.form["username"]
        new_password = request.form["password"]
        new_bio = request.form["bio"]

        user.username = new_username
        user.bio = new_bio

        if new_password:
            user.password = generate_password_hash(new_password)

        db.session.commit()

        session["user"] = new_username

        return redirect(f"/profile/{new_username}")

    return render_template("edit_profile.html", user=user)

@app.route("/post/<int:post_id>")
def view_post(post_id):

    post = Post.query.get_or_404(post_id)

    return render_template("post.html", post=post)

@app.route("/edit_post/<int:post_id>", methods=["GET", "POST"])
def edit_post(post_id):

    if "user" not in session:
        return redirect("/login")

    post = Post.query.get_or_404(post_id)

    if post.username != session["user"]:
        return "Not allowed"

    if request.method == "POST":
        post.content = request.form["content"]
        db.session.commit()
        return redirect("/profile/" + session["user"])

    return render_template("edit_post.html", post=post)

@app.route("/follow/<username>")
def follow(username):

    if "user" not in session:
        return redirect("/login")

    current_user = User.query.filter_by(
        username=session["user"]
    ).first()

    target_user = User.query.filter_by(
        username=username
    ).first()

    if not target_user:
        return redirect("/")

    if current_user.id == target_user.id:
        return redirect(f"/profile/{username}")

    existing = Follow.query.filter_by(
        follower_id=current_user.id,
        following_id=target_user.id
    ).first()

    if not existing:
        follow = Follow(
            follower_id=current_user.id,
            following_id=target_user.id
        )

        db.session.add(follow)
        db.session.commit()

    return redirect(f"/profile/{username}")

@app.route("/unfollow/<username>")
def unfollow(username):

    current_user = User.query.filter_by(
        username=session["user"]
    ).first()

    target_user = User.query.filter_by(
        username=username
    ).first()

    relationship = Follow.query.filter_by(
        follower_id=current_user.id,
        following_id=target_user.id
    ).first()

    if relationship:
        db.session.delete(relationship)
        db.session.commit()

    return redirect(f"/profile/{username}")

@app.route("/search")
def search():

    query = request.args.get("q", "")

    users = User.query.filter(
        User.username.contains(query)
    ).all()

    return render_template(
        "search.html",
        users=users,
        query=query
    )

@app.route("/delete_post/<int:post_id>")
def delete_post(post_id):

    if "user" not in session:
        return redirect("/login")

    post = Post.query.get_or_404(post_id)

    if post.username != session["user"]:
        return "Not authorized"

    db.session.delete(post)
    db.session.commit()

    return redirect("/")

@app.route("/reels")
def reels():
    posts = Post.query.filter(
        Post.video != ""
    ).order_by(Post.id.desc()).all()

    return render_template(
        "reels.html",
        posts=posts
    )

if __name__ == "__main__":
    socketio.run(app, debug=True)