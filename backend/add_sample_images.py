import os, sys, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from businesses.models import Business
from business_images.models import BusinessImage

# Get the large and medium businesses
large_biz = Business.objects.get(is_featured=True, featured_tier='large', name__icontains='Cosecha')
medium_biz = Business.objects.get(is_featured=True, featured_tier='medium', name__icontains='Futuro')

# Sample images from picsum.photos (restaurant/food themed)
large_images = [
    ('https://picsum.photos/seed/rest1/800/600', 'Plato principal'),
    ('https://picsum.photos/seed/rest2/800/600', 'Interior del restaurante'),
    ('https://picsum.photos/seed/rest3/800/600', 'Postre especial'),
    ('https://picsum.photos/seed/rest4/800/600', 'Terraza'),
    ('https://picsum.photos/seed/rest5/800/600', 'Chef preparando'),
]

medium_images = [
    ('https://picsum.photos/seed/edu1/800/600', 'Aula de clases'),
    ('https://picsum.photos/seed/edu2/800/600', 'Estudiantes'),
    ('https://picsum.photos/seed/edu3/800/600', 'Biblioteca'),
]

for i, (url, caption) in enumerate(large_images):
    BusinessImage.objects.create(business=large_biz, image=url, caption=caption, order=i)
    print(f"  Created: {caption} for {large_biz.name}")

for i, (url, caption) in enumerate(medium_images):
    BusinessImage.objects.create(business=medium_biz, image=url, caption=caption, order=i)
    print(f"  Created: {caption} for {medium_biz.name}")

print(f"\nDone! {BusinessImage.objects.count()} images created")
