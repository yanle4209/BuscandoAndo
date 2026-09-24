import os, django, random
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
django.setup()

from businesses.models import Business
from business_locations.models import BusinessLocation
from business_contacts.models import BusinessContact
from django.utils.text import slugify

PUB_PUBLICADO = 2
OP_ABIERTO = 1
OP_POR_HORARIO = 3

businesses_data = [
    {'name': 'Restaurante El Conuco', 'category': 1, 'desc': 'Comida tipica dominicana con el mejor sabor de la region.', 'short': 'Comida tipica dominicana.', 'street': 'Calle Principal #45', 'sector': 'Centro', 'municipality': 'Moca', 'province': 'Espaillat', 'lat': 19.3985, 'lng': -70.5226, 'phone': '809-555-0101'},
    {'name': 'Belleza Total Salon', 'category': 2, 'desc': 'Salon de belleza con servicios de corte, tintura y manicure.', 'short': 'Corte, tintura y manicure.', 'street': 'Av. La Paz #12', 'sector': 'Ensanche', 'municipality': 'Moca', 'province': 'Espaillat', 'lat': 19.3990, 'lng': -70.5210, 'phone': '809-555-0102'},
    {'name': 'Taller Mecanico Los Hermanos', 'category': 3, 'desc': 'Reparacion y mantenimiento de vehiculos automotrices.', 'short': 'Reparacion de vehiculos.', 'street': 'Carretera Moca #78', 'sector': 'Industrial', 'municipality': 'Moca', 'province': 'Espaillat', 'lat': 19.3970, 'lng': -70.5240, 'phone': '809-555-0103'},
    {'name': 'Clinica San Rafael', 'category': 4, 'desc': 'Clinica medica con servicios de laboratorio y imagenes.', 'short': 'Clinica medica completa.', 'street': 'Calle 12 #34', 'sector': 'Centro', 'municipality': 'Moca', 'province': 'Espaillat', 'lat': 19.3995, 'lng': -70.5230, 'phone': '809-555-0104'},
    {'name': 'Mi Tienda Express', 'category': 5, 'desc': 'Tienda de productos basicos y abarrotes.', 'short': 'Productos basicos y abarrotes.', 'street': 'Calle 5 #23', 'sector': 'Villa', 'municipality': 'Moca', 'province': 'Espaillat', 'lat': 19.3980, 'lng': -70.5215, 'phone': '809-555-0105'},
    {'name': 'Gimnasio FitLife', 'category': 6, 'desc': 'Gimnasio moderno con equipos de ultima generacion.', 'short': 'Gimnasio con equipos modernos.', 'street': 'Av. Independencia #56', 'sector': 'Ensanche', 'municipality': 'Moca', 'province': 'Espaillat', 'lat': 19.4000, 'lng': -70.5220, 'phone': '809-555-0106'},
    {'name': 'Escuela Bilingue Santa Maria', 'category': 7, 'desc': 'Escuela bilingue con enfoque en educacion integral.', 'short': 'Escuela bilingue integral.', 'street': 'Calle 8 #15', 'sector': 'Centro', 'municipality': 'Moca', 'province': 'Espaillat', 'lat': 19.3988, 'lng': -70.5235, 'phone': '809-555-0107'},
    {'name': 'Hotel Villa Moca', 'category': 8, 'desc': 'Hotel boutique con habitaciones comodas y piscina.', 'short': 'Hotel boutique con piscina.', 'street': 'Av. Turistica #10', 'sector': 'Turistico', 'municipality': 'Moca', 'province': 'Espaillat', 'lat': 19.4005, 'lng': -70.5205, 'phone': '809-555-0108'},
    {'name': 'Estudio Juridico Santana', 'category': 9, 'desc': 'Estudio de abogados especializado en derecho civil y penal.', 'short': 'Abogados civil y penal.', 'street': 'Calle 10 #28', 'sector': 'Centro', 'municipality': 'Moca', 'province': 'Espaillat', 'lat': 19.3992, 'lng': -70.5228, 'phone': '809-555-0109'},
    {'name': 'Tech Solutions Moca', 'category': 10, 'desc': 'Servicios de tecnologia y reparacion de computadoras.', 'short': 'Reparacion de computadoras.', 'street': 'Av. Tecnologica #5', 'sector': 'Industrial', 'municipality': 'Moca', 'province': 'Espaillat', 'lat': 19.3975, 'lng': -70.5245, 'phone': '809-555-0110'},
    {'name': 'Soda Dominicana', 'category': 1, 'desc': 'Restaurante de comida rapida dominicana.', 'short': 'Comida rapida dominicana.', 'street': 'Calle 3 #12', 'sector': 'Centro', 'municipality': 'Moca', 'province': 'Espaillat', 'lat': 19.3983, 'lng': -70.5218, 'phone': '809-555-0111'},
    {'name': 'Peluqueria Glamour', 'category': 2, 'desc': 'Peluqueria profesional con servicios de spa.', 'short': 'Peluqueria y spa.', 'street': 'Calle 7 #19', 'sector': 'Ensanche', 'municipality': 'Moca', 'province': 'Espaillat', 'lat': 19.3998, 'lng': -70.5212, 'phone': '809-555-0112'},
    {'name': 'Taller El Rayo', 'category': 3, 'desc': 'Servicio de mantenimiento automotriz y frenos.', 'short': 'Mantenimiento y frenos.', 'street': 'Carretera Sur #45', 'sector': 'Industrial', 'municipality': 'Moca', 'province': 'Espaillat', 'lat': 19.3968, 'lng': -70.5242, 'phone': '809-555-0113'},
    {'name': 'Laboratorio Clinico Moca', 'category': 4, 'desc': 'Laboratorio clinico con todos los examenes.', 'short': 'Laboratorio clinico completo.', 'street': 'Av. Salud #8', 'sector': 'Centro', 'municipality': 'Moca', 'province': 'Espaillat', 'lat': 19.3993, 'lng': -70.5232, 'phone': '809-555-0114'},
    {'name': 'Colmado La Esquina', 'category': 5, 'desc': 'Colmado con variedad de productos y bebidas.', 'short': 'Colmado completo.', 'street': 'Calle 2 #5', 'sector': 'Villa', 'municipality': 'Moca', 'province': 'Espaillat', 'lat': 19.3982, 'lng': -70.5216, 'phone': '809-555-0115'},
    {'name': 'CrossFit Moca', 'category': 6, 'desc': 'Clases de CrossFit y entrenamiento personalizado.', 'short': 'CrossFit y entrenamiento.', 'street': 'Av. Deportiva #22', 'sector': 'Deportivo', 'municipality': 'Moca', 'province': 'Espaillat', 'lat': 19.4002, 'lng': -70.5208, 'phone': '809-555-0116'},
    {'name': 'Academia de Ingles Global', 'category': 7, 'desc': 'Academia de idiomas con cursos para todos los niveles.', 'short': 'Cursos de ingles.', 'street': 'Calle 11 #30', 'sector': 'Centro', 'municipality': 'Moca', 'province': 'Espaillat', 'lat': 19.3991, 'lng': -70.5229, 'phone': '809-555-0117'},
    {'name': 'Resort Cibao', 'category': 8, 'desc': 'Resort con habitaciones de lujo y areas recreativas.', 'short': 'Resort de lujo.', 'street': 'Av. Turistica #20', 'sector': 'Turistico', 'municipality': 'Moca', 'province': 'Espaillat', 'lat': 19.4008, 'lng': -70.5202, 'phone': '809-555-0118'},
    {'name': 'Contador Express', 'category': 9, 'desc': 'Servicios de contabilidad y asesoria fiscal.', 'short': 'Contabilidad y asesoria fiscal.', 'street': 'Calle 9 #25', 'sector': 'Centro', 'municipality': 'Moca', 'province': 'Espaillat', 'lat': 19.3989, 'lng': -70.5233, 'phone': '809-555-0119'},
    {'name': 'Cyber Moca', 'category': 10, 'desc': 'Ciber cafe con servicios de impresion y fax.', 'short': 'Ciber cafe e impresiones.', 'street': 'Calle 4 #16', 'sector': 'Centro', 'municipality': 'Moca', 'province': 'Espaillat', 'lat': 19.3986, 'lng': -70.5222, 'phone': '809-555-0120'},
    {'name': 'Comedor La Abuela', 'category': 1, 'desc': 'Comida casera dominicana a precios accesibles.', 'short': 'Comida casera dominicana.', 'street': 'Calle 6 #9', 'sector': 'Centro', 'municipality': 'Moca', 'province': 'Espaillat', 'lat': 19.3984, 'lng': -70.5225, 'phone': '809-555-0121'},
    {'name': 'Barberia Clasica', 'category': 2, 'desc': 'Barberia masculina con cortes modernos.', 'short': 'Barberia masculina.', 'street': 'Calle 1 #8', 'sector': 'Centro', 'municipality': 'Moca', 'province': 'Espaillat', 'lat': 19.3981, 'lng': -70.5219, 'phone': '809-555-0122'},
]

FEATURED_COUNT = 5
created = 0

for i, data in enumerate(businesses_data):
    slug = slugify(data['name'])
    existing = Business.objects.filter(slug=slug).count()
    if existing > 0:
        slug = f"{slug}-{i+1}"

    biz = Business.objects.create(
        name=data['name'],
        slug=slug,
        description=data['desc'],
        short_description=data['short'],
        category_id=data['category'],
        publication_status_id=PUB_PUBLICADO,
        operational_status_id=random.choice([OP_ABIERTO, OP_POR_HORARIO]),
        is_featured=(i < FEATURED_COUNT),
        featured_permanent=(i < FEATURED_COUNT),
    )

    BusinessLocation.objects.create(
        business=biz,
        street=data['street'],
        sector=data['sector'],
        municipality=data['municipality'],
        province=data['province'],
        country='Republica Dominicana',
        latitude=data['lat'],
        longitude=data['lng'],
    )

    BusinessContact.objects.create(
        business=biz,
        phone=data['phone'],
    )

    created += 1
    feat = '*' if i < FEATURED_COUNT else ' '
    print("  {} [{:2d}] {}".format(feat, created, data['name']))

print(f"\nTotal created: {created}")
print(f"Featured: {Business.objects.filter(is_featured=True).count()}")
print(f"Published: {Business.objects.filter(publication_status_id=PUB_PUBLICADO).count()}")
