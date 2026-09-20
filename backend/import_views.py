"""
Vista de importación de negocios desde JSON.
Accesible desde el admin en /admin/import-json/
"""
import json
from django import forms
from django.contrib import admin
from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.urls import path, reverse

from businesses.models import Business
from categories.models import Category
from publication_status.models import PublicationStatus
from operational_status.models import OperationalStatus
from business_locations.models import BusinessLocation
from business_contacts.models import BusinessContact
from business_hours.models import BusinessHours


class JSONImportForm(forms.Form):
    json_file = forms.FileField(
        label='Archivo JSON',
        help_text='Selecciona un archivo .json con los negocios a importar.'
    )
    default_publication_status = forms.ChoiceField(
        label='Estado de publicación por defecto',
        choices=[],  # se llena en __init__
        initial='en-revision',
    )


def get_import_view():
    """Retorna la vista de importación (se llama desde urls.py)."""
    def import_json_view(request):
        if not request.user.is_staff:
            return redirect('admin:index')

        if request.method == 'POST':
            form = JSONImportForm(request.POST, request.FILES)
            if form.is_valid():
                json_file = request.FILES['json_file']
                pub_status_slug = form.cleaned_data['default_publication_status']

                try:
                    data = json.load(json_file)
                    if not isinstance(data, list):
                        data = [data]
                except json.JSONDecodeError as e:
                    messages.error(request, f'Error al leer JSON: {e}')
                    return render(request, 'admin/import_json.html', {'form': form})

                pub_status = PublicationStatus.objects.filter(slug=pub_status_slug).first()
                if not pub_status:
                    pub_status = PublicationStatus.objects.filter(slug='en-revision').first()

                created = 0
                skipped = 0
                errors = []

                for i, item in enumerate(data):
                    try:
                        slug = item.get('slug', '')
                        if not slug:
                            errors.append(f"Fila {i+1}: sin slug")
                            continue

                        if Business.objects.filter(slug=slug).exists():
                            skipped += 1
                            continue

                        # Category
                        category = None
                        cat_slug = item.get('category')
                        if cat_slug:
                            category = Category.objects.filter(slug=cat_slug).first()

                        # Operational status
                        op_status = None
                        op_slug = item.get('operational_status')
                        if op_slug:
                            op_status = OperationalStatus.objects.filter(slug=op_slug).first()

                        business = Business.objects.create(
                            name=item.get('name', ''),
                            slug=slug,
                            description=item.get('description', ''),
                            short_description=item.get('short_description', ''),
                            category=category,
                            publication_status=pub_status,
                            operational_status=op_status,
                            is_featured=item.get('is_featured', False),
                        )

                        # Location
                        loc = item.get('location', {})
                        if loc:
                            BusinessLocation.objects.create(
                                business=business,
                                street=loc.get('street', loc.get('address', '')),
                                sector=loc.get('sector', ''),
                                municipality=loc.get('municipality', loc.get('city', '')),
                                district=loc.get('district', ''),
                                province=loc.get('province', loc.get('state', '')),
                                postal_code=loc.get('postal_code', ''),
                                country=loc.get('country', 'República Dominicana'),
                                latitude=loc.get('latitude'),
                                longitude=loc.get('longitude'),
                            )

                        # Contact
                        contact = item.get('contact', {})
                        if contact:
                            BusinessContact.objects.create(
                                business=business,
                                phone=contact.get('phone', ''),
                                whatsapp=contact.get('whatsapp', ''),
                                email=contact.get('email', ''),
                                website=contact.get('website', ''),
                            )

                        # Hours
                        for h in item.get('hours', []):
                            BusinessHours.objects.create(
                                business=business,
                                day=h.get('day', ''),
                                open_time=h.get('open_time'),
                                close_time=h.get('close_time'),
                                is_closed=h.get('is_closed', False),
                            )

                        created += 1
                    except Exception as e:
                        errors.append(f"Fila {i+1} ({item.get('name', '?')}): {e}")

                msg = f'Importación completada: {created} creados, {skipped} omitidos.'
                if errors:
                    msg += f' {len(errors)} errores.'
                messages.success(request, msg)
                for err in errors[:10]:
                    messages.warning(request, err)

                return redirect('admin:businesses_business_changelist')
        else:
            form = JSONImportForm()

        context = {
            'form': form,
            'title': 'Importar Negocios desde JSON',
            'app_label': 'businesses',
            'opts': Business._meta,
        }
        return render(request, 'admin/import_json.html', context)

    return import_json_view


def get_export_view():
    """Retorna la vista de exportación JSON."""
    def export_json_view(request):
        if not request.user.is_staff:
            return redirect('admin:index')

        businesses = Business.objects.select_related(
            'category', 'publication_status', 'operational_status'
        ).prefetch_related(
            'location', 'contact', 'hours'
        ).all()

        data = []
        for b in businesses:
            item = {
                'name': b.name,
                'slug': b.slug,
                'description': b.description,
                'short_description': b.short_description,
                'category': b.category.slug if b.category else None,
                'publication_status': b.publication_status.slug if b.publication_status else None,
                'operational_status': b.operational_status.slug if b.operational_status else None,
                'is_featured': b.is_featured,
            }

            loc = getattr(b, 'location', None)
            if loc:
                item['location'] = {
                    'street': loc.street,
                    'sector': loc.sector,
                    'municipality': loc.municipality,
                    'district': loc.district,
                    'province': loc.province,
                    'postal_code': loc.postal_code,
                    'country': loc.country,
                    'latitude': float(loc.latitude) if loc.latitude else None,
                    'longitude': float(loc.longitude) if loc.longitude else None,
                }

            contact = getattr(b, 'contact', None)
            if contact:
                item['contact'] = {
                    'phone': contact.phone,
                    'whatsapp': contact.whatsapp,
                    'email': contact.email,
                    'website': contact.website,
                }

            hours = list(b.hours.all().order_by('day'))
            if hours:
                item['hours'] = [
                    {
                        'day': h.day,
                        'open_time': str(h.open_time) if h.open_time else None,
                        'close_time': str(h.close_time) if h.close_time else None,
                        'is_closed': h.is_closed,
                    }
                    for h in hours
                ]

            data.append(item)

        response = HttpResponse(
            json.dumps(data, ensure_ascii=False, indent=2),
            content_type='application/json'
        )
        response['Content-Disposition'] = 'attachment; filename="negocios_export.json"'
        return response

    return export_json_view
