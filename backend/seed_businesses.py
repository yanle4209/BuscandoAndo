import os, django, time
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
django.setup()
from businesses.models import Business
from business_locations.models import BusinessLocation
from business_contacts.models import BusinessContact
from business_hours.models import BusinessHours
from business_images.models import BusinessImage
from django.utils.text import slugify

pub_publicado_id = 2
op_abierto_id = 1
op_cerrado_id = 2
op_por_cerrar_id = 3

new_businesses = [
    # === RESTAURANTES ===
    {
        'name': 'Restaurante El Conuco',
        'category_id': 1,
        'description': 'Restaurante de comida típica dominicana con platos típicos del campo. Mofongo, mangú, asopao y más.',
        'short_description': 'Comida típica dominicana en ambiente rústico.',
        'phone': '809-555-0101', 'whatsapp': '8095550101', 'email': 'elconuco@gmail.com',
        'street': 'Av. Independencia #45', 'sector': 'Zona Colonial', 'municipality': 'Santo Domingo',
        'province': 'Distrito Nacional', 'lat': 18.4722, 'lng': -69.9125,
    },
    {
        'name': 'Sushi Tokio',
        'category_id': 1,
        'description': 'Restaurante japonés con los mejores sushi rolls y comida oriental de la ciudad.',
        'short_description': 'Sushi y comida japonesa premium.',
        'phone': '809-555-0102', 'whatsapp': '8095550102', 'email': 'sushitokio@gmail.com',
        'street': 'Av. Winston Churchill #120', 'sector': 'Piantini', 'municipality': 'Santo Domingo',
        'province': 'Distrito Nacional', 'lat': 18.4896, 'lng': -69.9296,
    },
    {
        'name': 'Pollo al Carbón El Tizon',
        'category_id': 1,
        'description': 'Pollo al carbón marinado con nuestra receta secreta. Acompañado de ensalada, yuca y tostones.',
        'short_description': 'El mejor pollo al carbón de la ciudad.',
        'phone': '809-555-0103', 'whatsapp': '8095550103',
        'street': 'Calle Las Américas #78', 'sector': 'Villa Mella', 'municipality': 'Santo Domingo Norte',
        'province': 'Santo Domingo', 'lat': 18.5164, 'lng': -69.8792,
    },
    # === BELLEZA ===
    {
        'name': 'Salón de Belleza Rosalía',
        'category_id': 2,
        'description': 'Salón de belleza completo con servicios de corte, tintes, alisados, manicure y pedicure.',
        'short_description': 'Tu belleza es nuestra pasión.',
        'phone': '809-555-0201', 'whatsapp': '8095550201', 'email': 'salonrosalia@gmail.com',
        'street': 'Calle María Teresa #34', 'sector': 'Naco', 'municipality': 'Santo Domingo',
        'province': 'Distrito Nacional', 'lat': 18.4945, 'lng': -69.9341,
    },
    {
        'name': 'Barbería The Kings',
        'category_id': 2,
        'description': 'Barbería moderna con estilo urbano. Cortes de cabello, barba y diseño de cejas.',
        'short_description': 'Cortes modernos para caballeros.',
        'phone': '809-555-0202', 'whatsapp': '8095550202',
        'street': 'Av. 27 de Febrero #200', 'sector': 'Mirador Sur', 'municipality': 'Santo Domingo',
        'province': 'Distrito Nacional', 'lat': 18.4743, 'lng': -69.9491,
    },
    # === TALLERES ===
    {
        'name': 'Taller Mecánico Express',
        'category_id': 3,
        'description': 'Servicio de mecánica general, latonería y pintura. Reparación de todo tipo de vehículos.',
        'short_description': 'Mecánica general y latonería.',
        'phone': '809-555-0301', 'whatsapp': '8095550301',
        'street': 'Autopista Duarte km 12', 'sector': 'Villa Consuelo', 'municipality': 'Santiago',
        'province': 'Santiago', 'lat': 19.4517, 'lng': -70.6880,
    },
    {
        'name': 'Taller Donde Juan',
        'category_id': 3,
        'description': 'Especialista en frenos, suspensión y alineación. Más de 20 años de experiencia.',
        'short_description': 'Frenos, suspensión y alineación.',
        'phone': '809-555-0302', 'whatsapp': '8095550302',
        'street': 'Calle Principal #56', 'sector': 'Industrial', 'municipality': 'San Pedro de Macorís',
        'province': 'San Pedro de Macorís', 'lat': 18.4553, 'lng': -69.3115,
    },
    # === CLINICAS ===
    {
        'name': 'Clínica Médica Santa María',
        'category_id': 4,
        'description': 'Clínica médica con consultas generales, laboratorio clínico, rayos X y ultrasonido.',
        'short_description': 'Atención médica integral.',
        'phone': '809-555-0401', 'whatsapp': '8095550401', 'email': 'clinicasantamaria@gmail.com',
        'street': 'Av. Abraham Lincoln #500', 'sector': 'Piantini', 'municipality': 'Santo Domingo',
        'province': 'Distrito Nacional', 'lat': 18.4925, 'lng': -70.6980,
    },
    {
        'name': 'Centro Odontológico Sonrisa',
        'category_id': 4,
        'description': 'Odontología general, ortodoncia, implantes dentales y estética dental.',
        'short_description': 'Tu sonrisa en buenas manos.',
        'phone': '809-555-0402', 'email': 'sonrisa.odo@gmail.com',
        'street': 'Calle Gustavo Mejía Ricart #80', 'sector': 'Naco', 'municipality': 'Santo Domingo',
        'province': 'Distrito Nacional', 'lat': 18.4967, 'lng': -69.9302,
    },
    # === TIENDAS ===
    {
        'name': 'Mini Market Doña Carmen',
        'category_id': 5,
        'description': 'Minimarket con productos de consumo diario, bebidas, snacks y productos frescos.',
        'short_description': 'Todo para tu día a día.',
        'phone': '809-555-0501', 'whatsapp': '8095550501',
        'street': 'Calle 12 #34', 'sector': 'Gualey', 'municipality': 'Santo Domingo',
        'province': 'Distrito Nacional', 'lat': 18.4665, 'lng': -69.9285,
    },
    {
        'name': 'Electro Mundo',
        'category_id': 5,
        'description': 'Tienda de electrodomésticos, artículos para el hogar y tecnología. Los mejores precios.',
        'short_description': 'Electrodomésticos y más.',
        'phone': '809-555-0502', 'email': 'electromundo@gmail.com',
        'street': 'Av. John F. Kennedy #300', 'sector': 'Ensanche Naco', 'municipality': 'Santo Domingo',
        'province': 'Distrito Nacional', 'lat': 18.4896, 'lng': -69.9341,
    },
    {
        'name': 'Moda Total',
        'category_id': 5,
        'description': 'Tienda de ropa femenina y masculina, accesorios y calzado. Marcas nacionales e importadas.',
        'short_description': 'Ropa y accesorios de moda.',
        'phone': '809-555-0503', 'whatsapp': '8095550503',
        'street': 'Calle El Conde #112', 'sector': 'Zona Colonial', 'municipality': 'Santo Domingo',
        'province': 'Distrito Nacional', 'lat': 18.4722, 'lng': -69.9195,
    },
    # === GIMNASIOS ===
    {
        'name': 'Gimnasio FitLife',
        'category_id': 6,
        'description': 'Gimnasio moderno con equipos de última generación, entrenadores personales y clases grupales.',
        'short_description': 'Tu salud es nuestra prioridad.',
        'phone': '809-555-0601', 'email': 'fitlife@gmail.com',
        'street': 'Av. Sarasota #85', 'sector': 'Santo Domingo', 'municipality': 'Santo Domingo',
        'province': 'Distrito Nacional', 'lat': 18.4854, 'lng': -69.9378,
    },
    {
        'name': 'CrossFit Santiago',
        'category_id': 6,
        'description': 'Box de CrossFit con entrenamiento funcional, halterofilia y movilidad.',
        'short_description': 'Entrenamiento funcional de alto rendimiento.',
        'phone': '809-555-0602', 'whatsapp': '8095550602',
        'street': 'Av. 27 de Febrero #150', 'sector': 'Centro del Norte', 'municipality': 'Santiago',
        'province': 'Santiago', 'lat': 19.4497, 'lng': -70.6920,
    },
    # === ESCUELAS ===
    {
        'name': 'Colegio Nuevo Horizonte',
        'category_id': 7,
        'description': 'Colegio bilingüe con educación inicial, primaria y secundaria. Enfoque en valores y tecnología.',
        'short_description': 'Educación bilingüe de calidad.',
        'phone': '809-555-0701', 'email': 'nuevohorizonte@gmail.com',
        'street': 'Av. John F. Kennedy #500', 'sector': 'Ensanche Palmira', 'municipality': 'Santiago',
        'province': 'Santiago', 'lat': 19.4580, 'lng': -70.6940,
    },
    {
        'name': 'Academia de Inglés Oxford',
        'category_id': 7,
        'description': 'Cursos de inglés para todos los niveles. Preparación para exámenes internacionales.',
        'short_description': 'Aprende inglés con los mejores.',
        'phone': '809-555-0702', 'email': 'oxford.ingles@gmail.com',
        'street': 'Calle Padre Castellanos #25', 'sector': 'Villa Progreso', 'municipality': 'Santo Domingo',
        'province': 'Distrito Nacional', 'lat': 18.4912, 'lng': -69.9270,
    },
    # === HOTELES ===
    {
        'name': 'Hotel Caribe Playa',
        'category_id': 8,
        'description': 'Hotel frente al mar con playa privada, piscina, restaurante y servicio de habitaciones 24 horas.',
        'short_description': 'Tu paraíso en la costa.',
        'phone': '809-555-0801', 'email': 'reservas@hotelcaribeplaya.com',
        'street': 'Playa Bávaro', 'sector': 'Punta Cana', 'municipality': 'Higüey',
        'province': 'La Altagracia', 'lat': 18.6809, 'lng': -68.4044,
    },
    {
        'name': 'Posada Colonial',
        'category_id': 8,
        'description': 'Posada boutique en la Zona Colonial con habitaciones decoradas al estilo dominicano colonial.',
        'short_description': 'Historia y confort en la Zona Colonial.',
        'phone': '809-555-0802', 'email': 'info@posadacolonial.do',
        'street': 'Calle Las Damas #8', 'sector': 'Zona Colonial', 'municipality': 'Santo Domingo',
        'province': 'Distrito Nacional', 'lat': 18.4690, 'lng': -69.9160,
    },
    # === SERVICIOS PROFESIONALES ===
    {
        'name': 'Despacho Legal Rodríguez & Asociados',
        'category_id': 9,
        'description': 'Despacho de abogados especializado en derecho civil, mercantil, laboral y familia.',
        'short_description': 'Soluciones legales para ti.',
        'phone': '809-555-0901', 'email': 'info@rodriguez-abogados.com',
        'street': 'Torre Empresarial #302', 'sector': 'Piantini', 'municipality': 'Santo Domingo',
        'province': 'Distrito Nacional', 'lat': 18.4900, 'lng': -70.6950,
    },
    {
        'name': 'Contadora María López',
        'category_id': 9,
        'description': 'Servicios contables, declaración de impuestos, auditoría y planificación fiscal.',
        'short_description': 'Contabilidad y fiscalidad.',
        'phone': '809-555-0902', 'email': 'marialopez.contador@gmail.com',
        'street': 'Av. Winston Churchill #200', 'sector': 'Torres del Parque', 'municipality': 'Santo Domingo',
        'province': 'Distrito Nacional', 'lat': 18.4880, 'lng': -69.9310,
    },
    {
        'name': 'Constructora EdificaRD',
        'category_id': 9,
        'description': 'Construcción y remodelación de viviendas, locales comerciales y oficinas.',
        'short_description': 'Construimos tus sueños.',
        'phone': '809-555-0903', 'whatsapp': '8095550903', 'email': 'info@edificard.com',
        'street': 'Av. Sarasota #120', 'sector': 'Santo Domingo', 'municipality': 'Santo Domingo',
        'province': 'Distrito Nacional', 'lat': 18.4830, 'lng': -69.9395,
    },
    # === TECNOLOGÍA ===
    {
        'name': 'TechStore RD',
        'category_id': 10,
        'description': 'Venta de computadoras, laptops, celulares, accesorios y repuestos. Servicio técnico incluido.',
        'short_description': 'Todo en tecnología.',
        'phone': '809-555-1001', 'whatsapp': '8095551001', 'email': 'ventas@techstore.do',
        'street': 'Av. 27 de Febrero #350', 'sector': 'Ensanche Quisqueya', 'municipality': 'Santo Domingo',
        'province': 'Distrito Nacional', 'lat': 18.4830, 'lng': -69.9420,
    },
    {
        'name': 'Soluciones Digitales Plus',
        'category_id': 10,
        'description': 'Desarrollo web, diseño gráfico, marketing digital y redes sociales para tu negocio.',
        'short_description': 'Tu presencia digital begins aquí.',
        'phone': '809-555-1002', 'email': 'info@solucionesdigitales.do',
        'street': 'Calle Roble #45', 'sector': 'Ciudad Nueva', 'municipality': 'Santiago',
        'province': 'Santiago', 'lat': 19.4470, 'lng': -70.6850,
    },
    # === MORE VARIETY ===
    {
        'name': 'Panadería La Tradición',
        'category_id': 1,
        'description': 'Panadería artesanal con pan dominicano, pastelitos, empanadas y café fresco desde las 5am.',
        'short_description': 'Pan fresco todos los días.',
        'phone': '809-555-1101', 'whatsapp': '8095551101',
        'street': 'Calle Mella #67', 'sector': 'Villa Consuelo', 'municipality': 'Santo Domingo',
        'province': 'Distrito Nacional', 'lat': 18.4650, 'lng': -69.9100,
    },
    {
        'name': 'Farmacia La Buena Vida',
        'category_id': 5,
        'description': 'Farmacia con medicamentos, productos de higiene, vitaminas y productos naturales.',
        'short_description': 'Tu salud a un clic.',
        'phone': '809-555-1201', 'email': 'labuenavida.farm@gmail.com',
        'street': 'Av. Independencia #300', 'sector': 'Villa Mella', 'municipality': 'Santo Domingo Norte',
        'province': 'Santo Domingo', 'lat': 18.5200, 'lng': -69.8850,
    },
    {
        'name': 'Veterinaria Patas y Colas',
        'category_id': 5,
        'description': 'Veterinaria con consultas, vacunas, cirugías, grooming y tienda de mascotas.',
        'short_description': 'Amor y cuidado para tus mascotas.',
        'phone': '809-555-1301', 'whatsapp': '8095551301', 'email': 'patasycolas@gmail.com',
        'street': 'Calle Primavera #12', 'sector': 'Los Mina', 'municipality': 'Santo Domingo',
        'province': 'Distrito Nacional', 'lat': 18.5020, 'lng': -69.8600,
    },
    {
        'name': 'Heladería Tropical',
        'category_id': 1,
        'description': 'Helados artesanales con sabores tropicales: guanábana, parcha, coconut, chocolate y más.',
        'short_description': 'Sabores tropicales en cada bocado.',
        'phone': '809-555-1401', 'whatsapp': '8095551401',
        'street': 'Malecón #45', 'sector': 'Puerto Malecón', 'municipality': 'Santo Domingo',
        'province': 'Distrito Nacional', 'lat': 18.4550, 'lng': -69.9150,
    },
    {
        'name': 'Academia de Arte Creativa',
        'category_id': 7,
        'description': 'Clases de pintura, escultura, cerámica y artes visuales para niños y adultos.',
        'short_description': 'Desarrolla tu lado artístico.',
        'phone': '809-555-1501', 'email': 'arte.creativa@gmail.com',
        'street': 'Calle Las Mercedes #23', 'sector': 'Zona Colonial', 'municipality': 'Santo Domingo',
        'province': 'Distrito Nacional', 'lat': 18.4705, 'lng': -69.9135,
    },
    {
        'name': 'Estudio Fotográfico Momento',
        'category_id': 9,
        'description': 'Fotografía profesional: bodas, quinceañeros, eventos corporativos y book fotográfico.',
        'short_description': 'Capturamos tus mejores momentos.',
        'phone': '809-555-1601', 'whatsapp': '8095551601', 'email': 'momento.foto@gmail.com',
        'street': 'Av. George Washington #500', 'sector': 'Malecón', 'municipality': 'Santo Domingo',
        'province': 'Distrito Nacional', 'lat': 18.4590, 'lng': -69.9180,
    },
    {
        'name': 'Ferretería El Martillo',
        'category_id': 5,
        'description': 'Ferretería completa con herramientas, materiales de construcción, plomería y electricidad.',
        'short_description': 'Todo para construir y reparar.',
        'phone': '809-555-1701',
        'street': 'Av. Mella #800', 'sector': 'Villa Consuelo', 'municipality': 'Santo Domingo',
        'province': 'Distrito Nacional', 'lat': 18.4620, 'lng': -69.9080,
    },
    {
        'name': 'Gimnasio Power Gym',
        'category_id': 6,
        'description': 'Gimnasio con pesas, cardio, spinning, zumba y entrenamiento personalizado.',
        'short_description': 'Pon tu cuerpo en movimiento.',
        'phone': '809-555-1801', 'whatsapp': '8095551801',
        'street': 'Av. 27 de Febrero #450', 'sector': 'Naco', 'municipality': 'Santo Domingo',
        'province': 'Distrito Nacional', 'lat': 18.4910, 'lng': -69.9360,
    },
    {
        'name': 'Pizza & Pasta Italiana',
        'category_id': 1,
        'description': 'Pizzas artesanales al horno de leña, pastas frescas y ensaladas. Ambiente familiar.',
        'short_description': 'Sabor italiano en RD.',
        'phone': '809-555-1901', 'email': 'info@pizzaitaliana.do',
        'street': 'Av. Abraham Lincoln #350', 'sector': 'Mirador Norte', 'municipality': 'Santo Domingo',
        'province': 'Distrito Nacional', 'lat': 18.4960, 'lng': -70.6930,
    },
    {
        'name': 'Peluquería Glamour Studio',
        'category_id': 2,
        'description': 'Peluquería de alta costura con cortes, tintes, tratamientos capilares y maquillaje.',
        'short_description': 'Estilo y elegancia.',
        'phone': '809-555-2001', 'whatsapp': '8095552001', 'email': 'glamour.studio@gmail.com',
        'street': 'Torre Empresarial #105', 'sector': 'Piantini', 'municipality': 'Santo Domingo',
        'province': 'Distrito Nacional', 'lat': 18.4910, 'lng': -70.6970,
    },
]

hours_template = [
    ('Lunes', '08:00', '18:00', False),
    ('Martes', '08:00', '18:00', False),
    ('Miércoles', '08:00', '18:00', False),
    ('Jueves', '08:00', '18:00', False),
    ('Viernes', '08:00', '18:00', False),
    ('Sábado', '09:00', '14:00', False),
    ('Domingo', None, None, True),
]

hours_restaurant = [
    ('Lunes', '11:00', '23:00', False),
    ('Martes', '11:00', '23:00', False),
    ('Miércoles', '11:00', '23:00', False),
    ('Jueves', '11:00', '23:00', False),
    ('Viernes', '11:00', '00:00', False),
    ('Sábado', '11:00', '00:00', False),
    ('Domingo', '11:00', '22:00', False),
]

hours_gym = [
    ('Lunes', '06:00', '22:00', False),
    ('Martes', '06:00', '22:00', False),
    ('Miércoles', '06:00', '22:00', False),
    ('Jueves', '06:00', '22:00', False),
    ('Viernes', '06:00', '22:00', False),
    ('Sábado', '07:00', '18:00', False),
    ('Domingo', '08:00', '14:00', False),
]

restaurant_cats = {1}

created = 0
for data in new_businesses:
    name = data['name']
    slug = slugify(name, allow_unicode=True)
    
    # Ensure unique slug
    base_slug = slug
    counter = 1
    while Business.objects.filter(slug=slug).exists():
        slug = f"{base_slug}-{counter}"
        counter += 1
    
    cat_id = data.get('category_id')
    if cat_id in restaurant_cats:
        hours_data = hours_restaurant
    elif cat_id == 6:
        hours_data = hours_gym
    else:
        hours_data = hours_template
    
    biz = Business.objects.create(
        name=name,
        slug=slug,
        description=data['description'],
        short_description=data.get('short_description', ''),
        category_id=cat_id,
        publication_status_id=pub_publicado_id,
        operational_status_id=op_abierto_id,
        is_featured=False,
    )
    
    BusinessLocation.objects.create(
        business=biz,
        street=data.get('street', ''),
        sector=data.get('sector', ''),
        municipality=data.get('municipality', ''),
        province=data.get('province', ''),
        latitude=data.get('lat'),
        longitude=data.get('lng'),
    )
    
    BusinessContact.objects.create(
        business=biz,
        phone=data.get('phone', ''),
        whatsapp=data.get('whatsapp', ''),
        email=data.get('email', ''),
    )
    
    for day_name, open_t, close_t, is_closed in hours_data:
        from datetime import time as dt_time
        open_time = dt_time.fromisoformat(open_t) if open_t else None
        close_time = dt_time.fromisoformat(close_t) if close_t else None
        BusinessHours.objects.create(
            business=biz,
            day=day_name,
            open_time=open_time,
            close_time=close_time,
            is_closed=is_closed,
        )
    
    created += 1
    print(f"  [{created:2d}] {name}")

print(f"\nTotal new businesses created: {created}")
print(f"Total businesses in DB: {Business.objects.count()}")
