"""
Lambda de transformation Bronze → Silver
Déclenchée par S3 Trigger sur les nouveaux fichiers velov.
Nettoie, normalise, ajoute features, écrit en Parquet partitionné.
Format source : GBFS v2.3 (JCDecaux/Cyclocity)
"""
import json
import os
import boto3
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import io
from datetime import datetime, timezone

BUCKET_BRONZE = os.environ['BUCKET_BRONZE']
BUCKET_SILVER = os.environ['BUCKET_SILVER']
GLUE_CRAWLER = os.environ.get('GLUE_CRAWLER', '')

s3 = boto3.client('s3')
glue = boto3.client('glue')


def parse_bronze_json(raw_body):
    """Extrait station_information et station_status depuis le JSON Bronze."""
    data = json.loads(raw_body)
    info = data.get('data', {}).get('station_information', {}).get('data', {}).get('stations', [])
    status = data.get('data', {}).get('station_status', {}).get('data', {}).get('stations', [])
    return info, status


def build_station_lookup(info_list):
    """Construit un dict station_id → info statique."""
    lookup = {}
    for s in info_list:
        sid = str(s.get('station_id', ''))
        lookup[sid] = {
            'name': s.get('name', ''),
            'lat': float(s.get('lat', 0)),
            'lon': float(s.get('lon', 0)),
            'address': s.get('address', ''),
            'capacity': int(s.get('capacity', 0))
        }
    return lookup


def extract_station_status(status_list, info_lookup, ingestion_ts):
    """Transforme les records GBFS status en DataFrame clean."""
    rows = []
    for s in status_list:
        sid = str(s.get('station_id', ''))
        info = info_lookup.get(sid, {})
        capacity = info.get('capacity', 0)
        bikes = int(s.get('num_bikes_available', 0))
        docks = int(s.get('num_docks_available', 0))
        total = bikes + docks
        fill_rate = bikes / capacity if capacity > 0 else (bikes / total if total > 0 else 0.0)

        status = 'OPEN'
        if not s.get('is_installed', True):
            status = 'CLOSED'
        elif not s.get('is_renting', True) and not s.get('is_returning', True):
            status = 'CLOSED'
        elif not s.get('is_renting', True):
            status = 'RETURN_ONLY'
        elif not s.get('is_returning', True):
            status = 'RENT_ONLY'

        rows.append({
            'station_id': sid,
            'name': info.get('name', ''),
            'lat': info.get('lat', 0.0),
            'lon': info.get('lon', 0.0),
            'address': info.get('address', ''),
            'capacity': capacity,
            'timestamp': ingestion_ts,
            'fill_rate': round(fill_rate, 4),
            'bikes_available': bikes,
            'docks_available': docks,
            'bikes_disabled': int(s.get('num_bikes_disabled', 0)),
            'docks_disabled': int(s.get('num_docks_disabled', 0)),
            'status': status,
            'last_reported': int(s.get('last_reported', 0))
        })
    return pd.DataFrame(rows)


def add_time_features(df):
    """Ajoute les features temporelles cycliques."""
    import math
    df['hour'] = df['timestamp'].dt.hour
    df['hour_sin'] = df['hour'].apply(lambda h: round(math.sin(2 * math.pi * h / 24), 4))
    df['hour_cos'] = df['hour'].apply(lambda h: round(math.cos(2 * math.pi * h / 24), 4))
    df['dow'] = df['timestamp'].dt.dayofweek
    df['dow_sin'] = df['dow'].apply(lambda d: round(math.sin(2 * math.pi * d / 7), 4))
    df['dow_cos'] = df['dow'].apply(lambda d: round(math.cos(2 * math.pi * d / 7), 4))
    df['is_weekend'] = df['dow'].isin([5, 6]).astype(int)
    return df


def write_partitioned_parquet(df, bucket, prefix, partition_cols):
    """Écrit un DataFrame en Parquet partitionné sur S3."""
    for _, group in df.groupby(partition_cols):
        date_val = group['timestamp'].iloc[0].strftime('%Y-%m-%d')
        station_val = group['station_id'].iloc[0]
        key = f"{prefix}/station_id={station_val}/date={date_val}/data.parquet"

        try:
            obj = s3.get_object(Bucket=bucket, Key=key)
            existing = pq.read_table(io.BytesIO(obj['Body'].read())).to_pandas()
            combined = pd.concat([existing, group], ignore_index=True)
        except s3.exceptions.NoSuchKey:
            combined = group

        combined = combined.drop_duplicates(subset=['station_id', 'timestamp'], keep='last')
        table = pa.Table.from_pandas(combined, preserve_index=False)
        buf = io.BytesIO()
        pq.write_table(table, buf, compression='snappy')
        s3.put_object(Bucket=bucket, Key=key, Body=buf.getvalue())


def handler(event, context):
    for record in event.get('Records', []):
        bucket = record['s3']['bucket']['name']
        key = record['s3']['object']['key']

        if not key.endswith('.json') or 'velov' not in key:
            continue

        obj = s3.get_object(Bucket=bucket, Key=key)
        info_list, status_list = parse_bronze_json(obj['Body'].read().decode('utf-8'))

        if not status_list:
            print(f"Aucune station trouvée dans {key}")
            continue

        info_lookup = build_station_lookup(info_list)
        ingestion_ts = datetime.now(timezone.utc)
        df = extract_station_status(status_list, info_lookup, ingestion_ts)
        df = add_time_features(df)

        write_partitioned_parquet(df, BUCKET_SILVER, 'status', ['station_id'])
        print(f"Transform OK : {len(df)} stations → s3://{BUCKET_SILVER}/status/")

    if GLUE_CRAWLER:
        try:
            glue.start_crawler(Name=GLUE_CRAWLER)
            print(f"Crawler {GLUE_CRAWLER} démarré")
        except Exception as e:
            print(f"Erreur crawler : {e}")

    return {'statusCode': 200, 'body': 'Transform OK'}
