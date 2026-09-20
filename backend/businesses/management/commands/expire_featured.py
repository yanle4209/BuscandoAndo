"""
Management command: python manage.py expire_featured
Desactiva destacados cuya fecha de fin haya pasado.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from businesses.models import Business


class Command(BaseCommand):
    help = 'Desactiva destacados vencidos (featured_end_date < now)'

    def handle(self, *args, **options):
        now = timezone.now()
        expired = Business.objects.filter(
            is_featured=True,
            featured_permanent=False,
            featured_end_date__isnull=False,
            featured_end_date__lt=now,
        )

        count = expired.count()
        if count == 0:
            self.stdout.write(self.style.SUCCESS('No hay destacados vencidos.'))
            return

        # Update each to clear featured
        for biz in expired:
            biz.is_featured = False
            biz.featured_tier = None
            biz.featured_start_date = None
            biz.featured_end_date = None
            biz.featured_weeks = None
            biz.featured_permanent = False
            biz.save()

        self.stdout.write(
            self.style.SUCCESS(f'{count} destacado(s) vencido(s) desactivado(s).')
        )
