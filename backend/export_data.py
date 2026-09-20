"""Export data from PostgreSQL to JSON fixture with UTF-8. ONLY businesses and related data."""
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

# Only export businesses and related models (NOT categories/statuses - those are created by load_initial_data)
apps_models = [
    'businesses.business',
    'business_locations.businesslocation',
    'business_contacts.businesscontact',
    'business_hours.businesshours',
    'business_images.businessimage',
]

objects = []
for model_label in apps_models:
    app_label, model_name = model_label.split('.')
    model = django.apps.apps.get_model(app_label, model_name)
    qs = model.objects.all()
    count = qs.count()
    if count > 0:
        print(f"  {model._meta.label}: {count}")
        data = serializers.serialize('json', qs, use_natural_foreign_keys=True, use_natural_primary_keys=True)
        objects.extend(json.loads(data))

output_path = os.path.join(os.path.dirname(__file__), 'initial_data.json')
with io.open(output_path, 'w', encoding='utf-8') as f:
    json.dump(objects, f, ensure_ascii=False, indent=2)

print(f"\nExported {len(objects)} objects to initial_data.json")
print(f"Size: {os.path.getsize(output_path) / 1024:.1f} KB")
