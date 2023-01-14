import functools
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from spotipy.cache_handler import FlaskSessionCacheHandler
from flask import (
    Blueprint,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from spotify_matcher.flaskr.db import get_db

bp = Blueprint("auth", __name__, url_prefix="/auth")


def get_oauth():
    oauth = SpotifyOAuth(
        scope="user-library-read",
        cache_handler=FlaskSessionCacheHandler(session),
        open_browser=False,
    )
    return oauth


def get_user(spotify_id):
    db = get_db()
    user = db.execute(
        "SELECT * FROM user WHERE spotify_id = ?", (spotify_id,)
    ).fetchone()
    return user


@bp.route("/login", methods=("GET", "POST"))
def login():
    oauth = get_oauth()
    return render_template("auth/login.html", authorize_url=oauth.get_authorize_url())


@bp.route("/callback")
def callback():
    state, auth_code = SpotifyOAuth.parse_auth_response_url(request.url)
    oauth = get_oauth()
    access_token = oauth.get_access_token(auth_code, as_dict=False)
    sp = spotipy.Spotify(auth=access_token)
    spotify_user = sp.me()
    db = get_db()
    user = get_user(spotify_user["id"])

    if user is None:
        db.execute(
            "INSERT INTO user (spotify_id, photo_url) VALUES (?, ?)",
            (
                spotify_user["id"],
                spotify_user["images"][0] if spotify_user["images"] else None,
            ),
        )
        db.commit()
        user = get_user(spotify_user["id"])
    g.user = user

    session.clear()
    session["user_id"] = user["id"]
    return redirect(url_for("index"))


@bp.before_app_request
def load_logged_in_user():
    user_id = session.get("user_id")

    if user_id is None:
        g.user = None
    else:
        g.user = (
            get_db().execute("SELECT * FROM user WHERE id = ?", (user_id,)).fetchone()
        )


@bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for("auth.login"))

        return view(**kwargs)

    return wrapped_view
