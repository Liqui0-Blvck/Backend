from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('business', '0001_initial'),
        ('notifications', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='WebhookSubscription',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('url', models.URLField(max_length=255)),
                ('secret_key', models.CharField(max_length=100)),
                ('is_active', models.BooleanField(default=True)),
                ('anuncios', models.BooleanField(default=True)),
                ('inventario', models.BooleanField(default=True)),
                ('ventas', models.BooleanField(default=True)),
                ('turnos', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('business', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='webhook_subscriptions', to='business.business')),
            ],
            options={
                'unique_together': {('business', 'url')},
            },
        ),
    ]
