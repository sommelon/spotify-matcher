import functools

import spotipy
from flask import Blueprint, g, redirect, render_template, request, session, url_for
from spotipy.cache_handler import FlaskSessionCacheHandler
from spotipy.oauth2 import SpotifyOAuth

from spotify_matcher.flaskr.db import get_db

bp = Blueprint("auth", __name__, url_prefix="/auth")


@bp.route("/login", methods=("GET", "POST"))
def login():
    if g.user:
        return redirect(url_for("invitation.invitations"))
    oauth = _get_oauth()
    return render_template("auth/login.html", authorize_url=oauth.get_authorize_url())


@bp.route("/callback")
def callback():
    state, auth_code = SpotifyOAuth.parse_auth_response_url(request.url)
    oauth = _get_oauth()
    access_token = oauth.get_access_token(auth_code, as_dict=False)
    sp = spotipy.Spotify(auth=access_token)
    spotify_user = sp.me()
    db = get_db()
    user = _get_user(spotify_user["id"])

    if user is None:
        with db.cursor() as cursor:
            cursor.execute(
                "INSERT INTO users (spotify_id, name, profile_url, photo_url) VALUES (%s, %s, %s, %s)",
                (
                    spotify_user["id"],
                    spotify_user["display_name"],
                    spotify_user["external_urls"]["spotify"],
                    spotify_user["images"][0]["url"]
                    if spotify_user["images"]
                    else None,
                ),
            )
        db.commit()
        user = _get_user(spotify_user["id"])
    g.user = user

    accepted_invitation = session.get("accepted_invitation")
    session.clear()
    session["user_id"] = user["id"]
    session["spotify_access_token"] = access_token
    if accepted_invitation:
        return redirect(
            url_for("invitation.invitation", invitation_id=accepted_invitation)
        )
    return redirect(url_for("invitation.invitations"))


@bp.before_app_request
def load_logged_in_user():
    user_id = session.get("user_id")

    if user_id is None:
        g.user = None
    else:
        with get_db().cursor() as cursor:
            cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
            user = cursor.fetchone()
        g.user = user


@bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))


def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for("auth.login"))

        return view(**kwargs)

    return wrapped_view


def _get_oauth():
    oauth = SpotifyOAuth(
        scope="user-library-read,playlist-read-private,user-top-read,user-read-recently-played,playlist-modify-private",
        cache_handler=FlaskSessionCacheHandler(session),
        open_browser=False,
    )
    return oauth


def _get_user(spotify_id):
    with get_db().cursor() as cursor:
        cursor.execute("SELECT * FROM users WHERE spotify_id = %s", (spotify_id,))
        user = cursor.fetchone()
    return user
