import os, django
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
django.setup()
from businesses.models import Business
from business_images.models import BusinessImage

# Add images to featured businesses that don't have any
featured_no_images = Business.objects.filter(is_featured=True).exclude(images__isnull=False)

image_sets = {
    'Peluquería Glamour Studio': [
        ('https://picsum.photos/seed/salon1/800/600', 'Interior del salón'),
        ('https://picsum.photos/seed/salon2/800/600', 'Corte de cabello'),
        ('https://picsum.photos/seed/salon3/800/600', 'Tinte profesional'),
    ],
    'Pizza & Pasta Italiana': [
        ('https://picsum.photos/seed/pizza1/800/600', 'Pizza artesanal'),
        ('https://picsum.photos/seed/pizza2/800/600', 'Pasta fresca'),
        ('https://picsum.photos/seed/pizza3/800/600', 'Restaurante'),
    ],
    'Gimnasio Power Gym': [
        ('https://picsum.photos/seed/gym1/800/600', 'Área de pesas'),
        ('https://picsum.photos/seed/gym2/800/600', 'Cardio'),
    ],
    'Ferretería El Martillo': [
        ('https://picsum.photos/seed/ferre1/800/600', 'Tienda'),
        ('https://picsum.photos/seed/ferre2/800/600', 'Herramientas'),
    ],
    'Estudio Fotográfico Momento': [
        ('https://picsum.photos/seed/foto1/800/600', 'Sesión de fotos'),
        ('https://picsum.photos/seed/foto2/800/600', 'Estudio'),
    ],
    'Heladería Tropical': [
        ('https://picsum.photos/seed/helado1/800/600', 'Helados tropicales'),
        ('https://picsum.photos/seed/helado2/800/600', 'Sabores'),
    ],
    'Academia de Arte Creativa': [
        ('https://picsum.photos/seed/arte1/800/600', 'Clase de pintura'),
        ('https://picsum.photos/seed/arte2/800/600', 'Obras de arte'),
    ],
    'Veterinaria Patas y Colas': [
        ('https://picsum.photos/seed/vet1/800/600', 'Consulta veterinaria'),
        ('https://picsum.photos/seed/vet2/800/600', 'Mascotas felices'),
    ],
    'Farmacia La Buena Vida': [
        ('https://picsum.photos/seed/farm2/800/600', 'Farmacia'),
    ],
    'Soluciones Digitales Plus': [
        ('https://picsum.photos/seed/tech1/800/600', 'Desarrollo web'),
        ('https://picsum.photos/seed/tech2/800/600', 'Marketing digital'),
    ],
}

count = 0
for biz in featured_no_images:
    imgs = image_sets.get(biz.name, [])
    if imgs:
        for i, (url, caption) in enumerate(imgs):
            BusinessImage.objects.create(
                business=biz,
                image=url,
                caption=caption,
                order=i,
            )
        count += 1
        print(f"  {biz.name}: {len(imgs)} images added")

print(f"\nAdded images to {count} businesses")
