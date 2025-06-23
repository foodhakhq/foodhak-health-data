from datetime import datetime
import json

class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

def json_serialize(obj):
    """Helper function to serialize objects to JSON, handling datetime objects"""
    return json.dumps(obj, cls=DateTimeEncoder) 