import re

from spotipy import Spotify

from spotify_matcher.flaskr import celery
from spotify_matcher.flaskr.db import get_db


def normalize_song(song):
    artist_ids = [artist["id"] for artist in song["artists"]]
    artists = ",".join(artist_ids)
    duration = song["duration_ms"] // 1000  # in seconds
    normalized_name = re.sub(r"\([^\)]+\)", "", song["name"]).strip()
    return {
        "name": song["name"],
        "artists": artists,
        "duration": duration,
        "url": song["external_link"],
        "hash": normalized_name + "-" + artist_ids + duration,
    }


def get_all_items(sp, results):
    items = results["items"]
    while results["next"]:
        results = sp.next(results)
        items.extend(results["items"])
    return items


@celery.task
def retrieve_songs(access_token, user):
    sp = Spotify(auth=access_token)
    liked_songs = sp.current_user_saved_tracks()["items"]
    playlists = sp.current_user_playlists(limit=50)
    playlists = get_all_items(playlists)
    playlists = [
        playlist
        for playlist in playlists["items"]
        if playlist["owner"]["id"] == user["spotify_id"]
    ]
    playlist_songs = []
    for playlist in playlists:
        playlist_songs = [
            sp.playlist_items(
                playlist["id"],
                limit=100,
                additional_types=("track",),
            )
        ]
        playlist_songs.extend(get_all_items(playlist_songs))
    songs = [normalize_song(song) for song in liked_songs + playlist_songs]
    db = get_db()
    db.commit()
    return songs
