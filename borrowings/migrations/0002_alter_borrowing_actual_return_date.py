# Generated by Django 4.2.5 on 2023-09-12 12:31

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("borrowings", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="borrowing",
            name="actual_return_date",
            field=models.DateTimeField(),
        ),
    ]
