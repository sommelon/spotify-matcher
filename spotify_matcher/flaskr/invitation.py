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
    return render_template("invitation/detail.html", invitation=invitation)


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
        from spotify_matcher.flaskr.tasks import retrieve_songs

        retrieve_songs.delay(session["spotify_access_token"], g.user["spotify_id"])
        if accepted_invitation:
            flash("Invitation already accepted.")
            return redirect(url_for("invitation.invitations"))

        cursor.execute(
            "INSERT INTO accepted_invitations (invitation_id, user_id) VALUES (%s, %s)",
            (invitation_id, g.user["id"]),
        )
        db.commit()

    return redirect(url_for("invitation.invitations"))


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
            "SELECT u.name, u.profile_url, u.photo_url FROM accepted_invitations i"
            " JOIN users u ON u.id = i.user_id"
            " WHERE invitation_id = %s",
            (invitation_id,),
        )
        accepted_invitations = cursor.fetchall()
    return accepted_invitations
