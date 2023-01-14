DROP TABLE IF EXISTS user;
DROP TABLE IF EXISTS post;

CREATE TABLE user (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  spotify_id TEXT NOT NULL
  photo_url TEXT,
);

CREATE TABLE invitation (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  uuid TEXT UNIQUE NOT NULL,
  author_id INTEGER NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (author_id) REFERENCES user (id)
);


CREATE TABLE accepted_invitation (
  invitation_id INTEGER NOT NULL,
  user_id INTEGER NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES user (id),
  FOREIGN KEY (invitation_id) REFERENCES invitation (id)
);


CREATE TABLE song (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  artists TEXT NOT NULL,
  duration INTEGER NOT NULL,
  album TEXT,
  year INTEGER,
  hash TEXT NOT NULL
);


CREATE TABLE user_song (
  user_id INTEGER NOT NULL,
  song_id INTEGER NOT NULL,
  source TEXT,
  FOREIGN KEY (user_id) REFERENCES user (id),
  FOREIGN KEY (song_id) REFERENCES song (id)
);