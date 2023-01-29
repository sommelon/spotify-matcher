import time
from uuid import uuid4

from dotenv import get_key
from flask import (
    Blueprint,
    abort,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from spotipy import Spotify, SpotifyException

from spotify_matcher.flaskr.auth import login_required
from spotify_matcher.flaskr.db import get_db

ALLOWED_SOURCES = [
    "owned_playlist",
    "not_owned_playlist",
    "liked_songs",
    "top_tracks",
    "recently_played",
]

bp = Blueprint("invitation", __name__, url_prefix="/invitations")


@bp.route("/")
@login_required
def invitations():
    with get_db().cursor() as cursor:
        cursor.execute(
            "SELECT id, created_at"
            " FROM invitations"
            " WHERE author_id = %s"
            " ORDER BY created_at DESC",
            (g.user["id"],),
        )
        invitations = cursor.fetchall()
    return render_template(
        "invitation/list.html",
        invitations=invitations,
        new_invitation_id=session.pop("new_invitation_id", None),
        get_accepted_invitations=_get_accepted_invitations,
    )


@bp.route("/<invitation_id>", methods=["GET", "POST"])
def invitation(invitation_id):
    with get_db().cursor() as cursor:
        cursor.execute(
            "SELECT i.id, i.author_id, u.name, u.photo_url, u.profile_url"
            " FROM users u JOIN invitations i ON i.author_id = u.id"
            " WHERE i.id = %s"
            " ORDER BY created_at DESC",
            (invitation_id,),
        )
        invitation = cursor.fetchone()

    accepted_invitations = _get_accepted_invitations(invitation_id)
    selected_sources = (
        request.form.keys() or ALLOWED_SOURCES
    )  # side effect: when user uncheckes everything, it checks everything again

    sources = tuple(source for source in selected_sources if source in ALLOWED_SOURCES)

    matches = _get_matches(invitation, accepted_invitations, sources)
    retrieving_songs = session.pop("retrieving_songs", False)

    return render_template(
        "invitation/detail.html",
        invitation=invitation,
        accepted_invitations=accepted_invitations,
        matches=matches,
        retrieving_songs=retrieving_songs,
        selected_sources=selected_sources,
    )


@bp.route("/accepted")
@login_required
def accepted_invitations():
    with get_db().cursor() as cursor:
        cursor.execute(
            "SELECT i.id, i.created_at"
            " FROM invitations i"
            " JOIN accepted_invitations ai ON ai.invitation_id = i.id AND ai.user_id = %s"
            " ORDER BY created_at DESC",
            (g.user["id"],),
        )
        invitations = cursor.fetchall()
    return render_template(
        "invitation/accepted.html",
        invitations=invitations,
        get_accepted_invitations=_get_accepted_invitations,
    )


def _get_matches(invitation, accepted_invitations, sources):
    if not accepted_invitations:
        return []

    user_ids = [user["id"] for user in accepted_invitations]
    matches = []
    with get_db().cursor() as cursor:
        if sources and invitation["author_id"] == g.user["id"]:
            cursor.execute(
                "SELECT DISTINCT s.id, s.name, s.url FROM songs s"
                " JOIN user_songs us ON s.id = us.song_id AND us.user_id = %s AND us.source IN %s",
                (invitation["author_id"], sources),
            )
        else:
            cursor.execute(
                "SELECT DISTINCT s.id, s.name, s.url FROM songs s"
                " JOIN user_songs us ON s.id = us.song_id AND us.user_id = %s",
                (invitation["author_id"],),
            )
        song_ids = tuple(song["id"] for song in cursor.fetchall())

        for user_id in user_ids:
            if not song_ids:
                break

            if sources and user_id == g.user["id"]:
                cursor.execute(
                    "SELECT DISTINCT s.id, s.name, s.url FROM songs s"
                    " JOIN user_songs us ON s.id = us.song_id AND us.user_id = %s AND s.id IN %s AND us.source IN %s",
                    (user_id, song_ids, sources),
                )
            else:
                cursor.execute(
                    "SELECT DISTINCT s.id, s.name, s.url FROM songs s"
                    " JOIN user_songs us ON s.id = us.song_id AND us.user_id = %s AND s.id IN %s",
                    (
                        user_id,
                        song_ids,
                    ),
                )
            song_ids = tuple(song["id"] for song in cursor.fetchall())

        if song_ids:
            cursor.execute(
                "SELECT id, name, url FROM songs s WHERE id IN %s",
                (song_ids,),
            )
            matches = cursor.fetchall()
    return matches


@bp.route("/<invitation_id>/save", methods=("POST",))
def save_matches(invitation_id):
    with get_db().cursor() as cursor:
        cursor.execute(
            "SELECT i.id, i.author_id, u.name, u.photo_url, u.profile_url"
            " FROM users u JOIN invitations i ON i.author_id = u.id"
            " WHERE i.id = %s"
            " ORDER BY created_at DESC",
            (invitation_id,),
        )
        invitation = cursor.fetchone()

    accepted_invitations = _get_accepted_invitations(invitation_id)
    selected_sources = (
        request.form.keys() or ALLOWED_SOURCES
    )  # side effect: when user uncheckes everything, it checks everything again

    sources = tuple(source for source in selected_sources if source in ALLOWED_SOURCES)
    matches = _get_matches(invitation, accepted_invitations, sources)

    from spotify_matcher.flaskr.tasks import save_matched_songs

    matched_users = [invitation["name"]] + [
        invitation["name"] for invitation in accepted_invitations
    ]

    if not _try_connection(session["spotify_access_token"]):
        return redirect(url_for("auth.login"))

    sp = Spotify(auth=session["spotify_access_token"])
    playlist = sp.user_playlist_create(
        g.user["spotify_id"],
        "Song matches: " + " + ".join(matched_users),
        public=False,
        description="Songs matched with " + ", ".join(matched_users),
    )
    save_matched_songs.delay(session["spotify_access_token"], g.user, playlist, matches)

    return render_template(
        "invitation/detail.html",
        invitation=invitation,
        accepted_invitations=accepted_invitations,
        matches=matches,
        new_playlist=playlist,
        selected_sources=selected_sources,
    )


@bp.route("/create", methods=("POST",))
@login_required
def create():
    db = get_db()
    uuid = str(uuid4())
    with db.cursor() as cursor:
        cursor.execute(
            "INSERT INTO invitations (id, author_id) VALUES (%s, %s)",
            (uuid, g.user["id"]),
        )
        cursor.execute("SELECT * FROM invitations WHERE id = %s", (uuid,))
        invitation = cursor.fetchone()
    db.commit()

    from spotify_matcher.flaskr.tasks import retrieve_songs

    if not _try_connection(session["spotify_access_token"]):
        return redirect(url_for("auth.login"))

    if not _get_fetched_songs_count():
        retrieve_songs.apply_async(
            (session["spotify_access_token"], g.user),
            task_id=f"{g.user['spotify_id']}-retrieve",
        )

    session["new_invitation_id"] = invitation["id"]
    flash("Invitation created successfuly. Copy the link and send it to someone.")
    return redirect(url_for("invitation.invitations"))


@bp.route("/accept/<invitation_id>", methods=("POST",))
def accept(invitation_id):
    if g.user is None:
        session["accepted_invitation"] = invitation_id
        return redirect(url_for("auth.login"))

    db = get_db()
    with db.cursor() as cursor:
        cursor.execute(
            "SELECT author_id FROM invitations WHERE id = %s", (invitation_id,)
        )
        invitation = cursor.fetchone()

        if g.user["id"] == invitation["author_id"]:
            flash("You can't accept your own invitation.")
            return abort(400)

        accepted_invitation = _get_accepted_invitation(invitation_id, g.user["id"])

        if accepted_invitation:
            flash("Invitation already accepted.")
            return redirect(
                url_for("invitation.invitation", invitation_id=invitation_id)
            )

        from spotify_matcher.flaskr.tasks import retrieve_songs

        if not _try_connection(session["spotify_access_token"]):
            return redirect(url_for("auth.login"))
        if not _get_fetched_songs_count():
            retrieve_songs.apply_async(
                (session["spotify_access_token"], g.user),
                task_id=f"{g.user['spotify_id']}-retrieve",
            )

        cursor.execute(
            "INSERT INTO accepted_invitations (invitation_id, user_id) VALUES (%s, %s)",
            (invitation_id, g.user["id"]),
        )
        db.commit()
    session["retrieving_songs"] = True
    return redirect(url_for("invitation.invitation", invitation_id=invitation_id))


@bp.route("/fetch", methods=("POST",))
def fetch():
    from spotify_matcher.flaskr.tasks import retrieve_songs

    if not _try_connection(session["spotify_access_token"]):
        return redirect(url_for("auth.login"))
    seconds_since_last_fetch = int(time.time()) - g.user["last_song_retrieval_time"]
    song_cache_time = int(get_key(".env", "SONG_CACHE_TIME"))

    print("Retrieving songs for user", g.user["name"])
    if g.user["last_song_retrieval_time"] is not None:
        if seconds_since_last_fetch < song_cache_time:
            print("Getting songs from cache.")
            flash(
                f"Sorry, we don't want to annoy Spotify do we? You can fetch songs again after {song_cache_time - seconds_since_last_fetch} seconds."
            )
        else:
            task_id = f"{g.user['spotify_id']}-retrieve"
            retrieve_songs.apply_async(
                (session["spotify_access_token"], g.user),
                task_id=task_id,
            )

    next = request.args.get("next", url_for("invitation.invitations"))
    return redirect(next)


@bp.route("fetch/status")
def fetch_status():
    if not g.user:
        return {}

    from spotify_matcher.flaskr import celery

    task_id = f"{g.user['spotify_id']}-retrieve"
    res = celery.AsyncResult(task_id)
    if res.status != "STARTED":
        res.forget()
    return jsonify(status=res.status)


@bp.route("fetched-songs-count")
def fetched_songs_count():
    if not g.user:
        return {}
    return jsonify(count=_get_fetched_songs_count())


def _get_accepted_invitation(invitation_id, user_id):
    with get_db().cursor() as cursor:
        cursor.execute(
            "SELECT * FROM accepted_invitations WHERE invitation_id = %s AND user_id = %s",
            (invitation_id, user_id),
        )
        accepted_invitation = cursor.fetchone()
    return accepted_invitation


def _get_accepted_invitations(invitation_id):
    with get_db().cursor() as cursor:
        cursor.execute(
            "SELECT u.id, u.name, u.profile_url, u.photo_url FROM accepted_invitations i"
            " JOIN users u ON u.id = i.user_id"
            " WHERE invitation_id = %s",
            (invitation_id,),
        )
        accepted_invitations = cursor.fetchall()
    return accepted_invitations


def _try_connection(access_token):
    sp = Spotify(auth=access_token)
    try:
        sp.me()
        return True
    except SpotifyException as e:
        accepted_invitation = session.get("accepted_invitation")
        session.clear()
        if accepted_invitation:
            session["accepted_invitation"] = accepted_invitation
        if "expired" in e.msg:
            flash("Your Spotify token has expired, you need to log in again.")
        else:
            flash("Unexpected error: " + e.msg)
        return False


def _get_fetched_songs_count():
    with get_db().cursor() as cursor:
        cursor.execute(
            "SELECT count(DISTINCT song_id) FROM user_songs WHERE user_id = %s",
            (g.user["id"],),
        )
        count = cursor.fetchall()
    return count[0]["count"] if count else 0
