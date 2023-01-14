from flask import Blueprint, g, redirect, render_template, request, url_for, flash
from spotify_matcher.flaskr.auth import login_required
from spotify_matcher.flaskr.db import get_db
from uuid import uuid4

bp = Blueprint("invitation", __name__)


@bp.route("/")
@login_required
def index():
    db = get_db()
    invitations = db.execute(
        "SELECT i.id, i.uuid, created_at"
        " FROM invitation i JOIN user u ON i.author_id = ?"
        " ORDER BY created_at DESC",
        (g.user["id"],),
    ).fetchall()
    invitations = [dict(row) for row in invitations]
    return render_template("invitation/index.html", invitations=invitations)


@bp.route("/create", methods=("GET", "POST"))
@login_required
def create():
    if request.method == "POST":
        db = get_db()
        uuid = str(uuid4())
        db.execute(
            "INSERT INTO invitation (uuid, author_id) VALUES (?, ?)",
            (uuid, g.user["id"]),
        )
        db.commit()
        invitation = db.execute(
            "SELECT * FROM invitation WHERE uuid = ?", (uuid,)
        ).fetchone()
        flash(dict(invitation), "new_invitation")
        return redirect(url_for("invitation.index"))

    return render_template("invitation/create.html")
