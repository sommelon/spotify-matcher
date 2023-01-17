import re
import time

from dotenv import get_key
from psycopg2.extensions import cursor as _cursor
from psycopg2.extras import execute_values
from spotipy import Spotify

from spotify_matcher.flaskr import celery
from spotify_matcher.flaskr.db import get_db


def normalize_song_name(song_name):
    normalized_name = re.sub(
        r"\([^\)]*LIVE[^\)]*\)", "", song_name, flags=re.IGNORECASE
    ).strip()
    normalized_name = re.sub(
        r"- ?\w* Live( Version)?$", "", normalized_name, flags=re.IGNORECASE
    ).strip()
    normalized_name = re.sub(
        r"\(\w* (Remix|Remastere?d?)\)$", "", normalized_name, flags=re.IGNORECASE
    ).strip()
    normalized_name = re.sub(
        r" ?\w* (Remix|Remastere?d?)$", "", normalized_name, flags=re.IGNORECASE
    ).strip()
    return normalized_name


def normalize_song(song):
    artist_ids = ",".join([artist["id"] for artist in song["artists"]])
    normalized_name = normalize_song_name(song["name"])
    return {
        "name": normalized_name,
        "artists": artist_ids,
        "url": song["external_urls"]["spotify"],
        "hash": f"{song['artists'][0]['id']}-{normalized_name}",
    }


def collect_all_items(sp, results):
    for item in results["items"]:
        yield item

    while results["next"]:
        results = sp.next(results)
        for item in results["items"]:
            yield item


def _filter_songs(songs: list):
    with get_db().cursor() as cursor:
        song_hashes = tuple([song["hash"] for song in songs])
        cursor.execute("SELECT id, hash FROM songs WHERE hash IN %s", (song_hashes,))
        existing_songs_db = cursor.fetchall()

    new_songs = []
    existing_songs = []
    for song in songs:
        existing_song = next(
            (
                existing_song
                for existing_song in existing_songs_db
                if song["hash"] == existing_song["hash"]
            ),
            None,
        )
        if existing_song:
            song["id"] = existing_song["id"]
            existing_songs.append(song)
        else:
            new_songs.append(song)
    return existing_songs, new_songs


@celery.task
def retrieve_songs(access_token, user):
    print("Retrieving songs for user", user["name"])
    if user["last_song_retrieval_time"] is not None:
        if int(time.time()) - user["last_song_retrieval_time"] < int(
            get_key(".env", "SONG_CACHE_TIME")
        ):
            print("Getting songs from cache.")
            return

    sp = Spotify(auth=access_token)
    liked_songs = sp.current_user_saved_tracks()
    liked_songs = [
        normalize_song(song["track"]) for song in collect_all_items(sp, liked_songs)
    ]

    playlists = sp.current_user_playlists()
    playlists = [
        playlist
        for playlist in collect_all_items(sp, playlists)
        if playlist["owner"]["id"] == user["spotify_id"]
    ]
    print("Retrieved", len(playlists), "owner's playlists")
    playlist_songs = []
    for playlist in playlists:
        playlist_items = sp.playlist_items(
            playlist["id"],
            limit=100,
            additional_types=("track",),
        )
        songs = [
            normalize_song(song["track"])
            for song in collect_all_items(sp, playlist_items)
        ]
        playlist_songs.extend(songs)

    top_tracks = sp.current_user_top_tracks()
    top_tracks = [normalize_song(song) for song in collect_all_items(sp, top_tracks)]

    recently_played = sp.current_user_recently_played()
    recently_played = [
        normalize_song(song["track"]) for song in collect_all_items(sp, recently_played)
    ]

    all_songs = liked_songs + playlist_songs + top_tracks + recently_played
    print("Retrieved", len(all_songs), "songs")
    existing_songs, new_songs = _filter_songs(all_songs)
    new_songs = {(s["name"], s["artists"], s["url"], s["hash"]) for s in new_songs}
    db = get_db()
    with db.cursor(cursor_factory=_cursor) as cursor:
        new_song_ids = execute_values(
            cursor,
            "INSERT INTO songs (name, artists, url, hash) VALUES %s RETURNING id",
            new_songs,
            fetch=True,
        )
        print("Added", len(new_song_ids), "new songs")

    all_song_ids = tuple(id[0] for id in new_song_ids) + tuple(
        song["id"] for song in existing_songs
    )
    with db.cursor() as cursor:
        execute_values(
            cursor,
            "INSERT INTO user_songs (user_id, song_id, source) VALUES %s ON CONFLICT DO NOTHING",
            [(user["id"], id, "playlist") for id in all_song_ids],
        )

    db.commit()
    with db.cursor() as cursor:
        cursor.execute(
            "UPDATE users SET last_song_retrieval_time = %s WHERE id = %s",
            (int(time.time()), user["id"]),
        )
    db.commit()
    return songs


@celery.task
def save_matched_songs(access_token, user, matches, matched_users):
    sp = Spotify(auth=access_token)
    playlist = sp.user_playlist_create(
        user["spotify_id"],
        "Song matches: " + ",".join(matched_users),
        public=False,
        description="Songs matched with " + ", ".join(matched_users),
    )

    max_simultaneous_songs = 50
    songs_in_chunks = [
        matches[x : x + max_simultaneous_songs]  # noqa
        for x in range(0, len(matches), max_simultaneous_songs)
    ]
    for chunk in songs_in_chunks:
        sp.playlist_add_items(playlist["id"], [song["url"] for song in chunk])
