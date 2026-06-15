CREATE TABLE IF NOT EXISTS utilisateurs (
    id               SERIAL PRIMARY KEY,
    nom              VARCHAR NOT NULL,
    prenom           VARCHAR NOT NULL,
    email            VARCHAR UNIQUE NOT NULL,
    hashed_password  VARCHAR NOT NULL,
    role             VARCHAR NOT NULL DEFAULT 'user',  -- 'user' | 'analyste' | 'admin'
    created_at       TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_utilisateurs_email ON utilisateurs (email);




CREATE TABLE IF NOT EXISTS historique_stations (
    id                    SERIAL PRIMARY KEY,
    station_id            VARCHAR NOT NULL,
    fill_rate             FLOAT NOT NULL,
    num_bikes_available   INTEGER NOT NULL,
    num_docks_available   INTEGER NOT NULL,
    status                VARCHAR NOT NULL, 
    timestamp             TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_historique_station_id ON historique_stations (station_id);
CREATE INDEX IF NOT EXISTS idx_historique_timestamp   ON historique_stations (timestamp);


