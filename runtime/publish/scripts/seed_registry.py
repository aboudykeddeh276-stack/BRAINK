import json, os
from braink_runtime.storage import Store
root=os.getenv('BRAINK_DATA_DIR','./data'); s=Store(root)
for obj in json.load(open('seed_registry.json')): s.put_object(obj['object_id'],obj)
print(json.dumps({'seeded':len(s.list_objects()),'data_dir':root}))
