import json

def pretty_json(data):
    try:
        return json.dumps(data, indent=4, sort_keys=True)
    except:
        return str(data)
