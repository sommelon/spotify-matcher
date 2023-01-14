from flask import (
    Blueprint,
    g,
    redirect,
    render_template,
    url_for,
    flash,
    session,
    abort,
)
from spotify_matcher.flaskr.auth import login_required
from spotify_matcher.flaskr.db import get_db
from uuid import uuid4

bp = Blueprint("invitation", __name__, url_prefix="/invitations")


@bp.route("/")
@login_required
def invitations():
    db = get_db()
    invitations = db.execute(
        "SELECT id, created_at"
        " FROM invitation"
        " WHERE author_id = ?"
        " ORDER BY created_at DESC",
        (g.user["id"],),
    ).fetchall()
    invitations = [dict(row) for row in invitations]
    return render_template(
        "invitation/list.html",
        invitations=invitations,
        get_accepted_invitations=_get_accepted_invitations,
    )


@bp.route("/<invitation_id>")
@login_required
def invitation(invitation_id):
    db = get_db()
    invitation = db.execute(
        "SELECT i.id, i.author_id, u.name, u.photo_url, u.profile_url"
        " FROM user u JOIN invitation i ON i.author_id = u.id"
        " WHERE i.id = ?"
        " ORDER BY created_at DESC",
        (invitation_id,),
    ).fetchone()
    return render_template("invitation/detail.html", invitation=invitation)


@bp.route("/create", methods=("POST",))
@login_required
def create():
    db = get_db()
    uuid = str(uuid4())
    db.execute(
        "INSERT INTO invitation (id, author_id) VALUES (?, ?)",
        (uuid, g.user["id"]),
    )
    db.commit()
    invitation = db.execute("SELECT * FROM invitation WHERE id = ?", (uuid,)).fetchone()
    flash(dict(invitation), "new_invitation")
    return redirect(url_for("invitation.invitations"))


@bp.route("/accept/<invitation_id>", methods=("POST",))
def accept(invitation_id):
    if g.user is None:
        session["accepted_invitation"] = invitation_id
        return redirect(url_for("auth.login"))

    db = get_db()
    invitation = db.execute(
        "SELECT author_id FROM invitation WHERE id = ?", (invitation_id,)
    ).fetchone()
    if g.user["id"] == invitation["author_id"]:
        flash("You can't accept your own invitation.")
        return abort(400)

    accepted_invitation = _get_accepted_invitation(invitation_id, g.user["id"])
    if accepted_invitation:
        flash("Invitation already accepted.")
        return redirect(url_for("invitation.invitations"))

    db.execute(
        "INSERT INTO accepted_invitation (invitation_id, user_id) VALUES (?, ?)",
        (invitation_id, g.user["id"]),
    )
    db.commit()

    return redirect(url_for("invitation.invitations"))


def _get_accepted_invitation(invitation_id, user_id):
    db = get_db()
    accepted_invitation = db.execute(
        "SELECT * FROM accepted_invitation WHERE invitation_id = ? AND user_id = ?",
        (invitation_id, user_id),
    ).fetchone()
    return dict(accepted_invitation) if accepted_invitation else None


def _get_accepted_invitations(invitation_id):
    db = get_db()
    accepted_invitations = db.execute(
        "SELECT u.name, u.profile_url, u.photo_url FROM accepted_invitation i"
        " JOIN user u ON u.id = i.user_id"
        " WHERE invitation_id = ?",
        (invitation_id,),
    ).fetchall()
    accepted_invitations = [dict(accepted) for accepted in accepted_invitations]
    return accepted_invitations
