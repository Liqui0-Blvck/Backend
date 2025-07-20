from django.db import models
from simple_history.models import HistoricalRecords

class BaseHistoricalModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    history = HistoricalRecords(inherit=True)  # Añadir inherit=True aquí

    class Meta:
        abstract = True
        
        
class BaseModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        abstract = True