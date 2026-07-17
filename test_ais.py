import json

msg_str = '''{
  "MetaData": {
    "MMSI": 219028045,
    "MMSI_String": 219028045,
    "ShipName": " TERN ",
    "latitude": 54.218575,
    "longitude": 11.082728,
    "time_utc": "2023-01-26 14:00:39.141634863 +0000 UTC"
  }
}'''
msg = json.loads(msg_str)
print(msg["MetaData"].get("latitude"))
