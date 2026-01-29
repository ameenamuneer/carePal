from django.urls import path
from . import views

urlpatterns = [
    path('vitals/<int:vitals_id>/export/', views.get_vitals_as_fhir, name='vitals-fhir-export'),
    # Note: Using int:vitals_id because in Django generic keys are usually int, but VitalReading might use auto-int.
    # Wait, VitalReading definition provided by tool showed: class VitalReading(models.Model): ... id (auto). 
    # Usually ID is AutoField (int). The user example used UUID. I should check if my model uses UUID.
    # Result of view_file models.py: Line 143: class VitalReading(models.Model). No ID specified -> AutoField (Int).
    # So <int:vitals_id> is correct.
]
