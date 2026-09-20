"""Export data from PostgreSQL to JSON fixture with UTF-8."""
import os, sys, io, json
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
os.environ['USE_POSTGRES'] = 'True'
os.environ['DB_NAME'] = 'buscandoando'
os.environ['DB_USER'] = 'postgres'
os.environ['DB_PASSWORD'] = 'Monster'
os.environ['DB_HOST'] = 'localhost'

import django
django.setup()

from django.core import serializers

apps = ['categories', 'publication_status', 'operational_status',
        'businesses', 'business_locations', 'business_contacts',
        'business_hours', 'business_images']

objects = []
for app in apps:
    models = django.apps.apps.get_app_config(app).get_models()
    for model in models:
        qs = model.objects.all()
        count = qs.count()
        if count > 0:
            print(f"  {model._meta.label}: {count}")
            # Use Django's json serializer to handle datetime etc.
            data = serializers.serialize('json', qs, use_natural_foreign_keys=True, use_natural_primary_keys=True)
            objects.extend(json.loads(data))

output_path = os.path.join(os.path.dirname(__file__), 'initial_data.json')
with io.open(output_path, 'w', encoding='utf-8') as f:
    json.dump(objects, f, ensure_ascii=False, indent=2)

print(f"\nExported {len(objects)} objects to initial_data.json")
print(f"Size: {os.path.getsize(output_path) / 1024:.1f} KB")
