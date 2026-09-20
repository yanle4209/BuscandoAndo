from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("businesses", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="business",
            name="featured_tier",
            field=models.CharField(
                blank=True,
                choices=[
                    ("large", "Grande"),
                    ("medium", "Mediano"),
                    ("small", "Pequeño"),
                ],
                help_text="Nivel de destacado: large = 2 columnas + 2 filas, medium = 2 columnas, small = 1 columna",
                max_length=10,
                null=True,
            ),
        ),
    ]
