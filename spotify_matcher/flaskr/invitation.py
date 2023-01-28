from uuid import uuid4

from flask import (
    Blueprint,
    abort,
    flash,
    g,
    redirect,
    render_template,
    session,
    url_for,
)
from spotipy import Spotify, SpotifyException

from spotify_matcher.flaskr.auth import login_required
from spotify_matcher.flaskr.db import get_db

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
        get_accepted_invitations=_get_accepted_invitations,
    )


@bp.route("/<invitation_id>")
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
    matches = _get_matches(invitation, accepted_invitations)
    retrieving_songs = session.pop("retrieving_songs", False)

    return render_template(
        "invitation/detail.html",
        invitation=invitation,
        accepted_invitations=accepted_invitations,
        matches=matches,
        retrieving_songs=retrieving_songs,
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


def _get_matches(invitation, accepted_invitations):
    if not accepted_invitations:
        return []

    user_ids = [user["id"] for user in accepted_invitations]
    matches = []
    with get_db().cursor() as cursor:
        cursor.execute(
            "SELECT DISTINCT s.id, s.name, s.url FROM songs s"
            " JOIN user_songs us ON s.id = us.song_id AND us.user_id = %s",
            (invitation["author_id"],),
        )
        song_ids = tuple(song["id"] for song in cursor.fetchall())

        for id_ in user_ids:
            if not song_ids:
                break

            cursor.execute(
                "SELECT DISTINCT s.id, s.name, s.url FROM songs s"
                " JOIN user_songs us ON s.id = us.song_id AND us.user_id = %s AND s.id IN %s",
                (id_, song_ids),
            )
            song_ids = tuple(song["id"] for song in cursor.fetchall())

        if song_ids:
            cursor.execute(
                "SELECT id, name, url FROM songs s WHERE id IN %s",
                (song_ids,),
            )
            matches = cursor.fetchall()
    return matches


@bp.route("/<invitation_id>", methods=("POST",))
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
    matches = _get_matches(invitation, accepted_invitations)

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

    retrieve_songs.delay(session["spotify_access_token"], g.user)

    flash(invitation, "new_invitation")
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
        retrieve_songs.delay(session["spotify_access_token"], g.user)

        cursor.execute(
            "INSERT INTO accepted_invitations (invitation_id, user_id) VALUES (%s, %s)",
            (invitation_id, g.user["id"]),
        )
        db.commit()
    session["retrieving_songs"] = True
    return redirect(url_for("invitation.invitation", invitation_id=invitation_id))


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
