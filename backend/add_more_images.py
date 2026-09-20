import os, django
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
django.setup()
from businesses.models import Business
from business_images.models import BusinessImage

more_images = {
    'Pizzería Don Mario': [
        ('https://picsum.photos/seed/donmario1/800/600', 'Pizza especial'),
        ('https://picsum.photos/seed/donmario2/800/600', 'Interior'),
        ('https://picsum.photos/seed/donmario3/800/600', 'Horno de leña'),
    ],
    'Veterinaria Patitas Felices': [
        ('https://picsum.photos/seed/patitas1/800/600', 'Consulta'),
        ('https://picsum.photos/seed/patitas2/800/600', 'Mascotas'),
    ],
}

for biz_name, imgs in more_images.items():
    biz = Business.objects.get(name=biz_name)
    for i, (url, caption) in enumerate(imgs):
        BusinessImage.objects.create(business=biz, image=url, caption=caption, order=i)
    print(f"  {biz_name}: {len(imgs)} images added")
