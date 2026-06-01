from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('agent', '0003_agentaction_agentcacheentry_agenteventlog_and_more'),
        ('patients', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='PatientActivityLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('activity_type', models.CharField(
                    choices=[
                        ('MEAL', 'Meal / Eating'),
                        ('EXERCISE', 'Physical Activity / Exercise'),
                        ('SLEEP', 'Sleep / Rest'),
                        ('SYMPTOM', 'Symptom Reported'),
                        ('MEDICATION', 'Medication Related'),
                        ('MOOD', 'Mood / Emotional State'),
                        ('VITAL_OBSERVATION', 'Vital Sign Observation'),
                        ('BEHAVIOR', 'Behavioral Pattern'),
                        ('SOCIAL', 'Social Activity'),
                        ('ENVIRONMENT', 'Environment / Location'),
                        ('OTHER', 'Other'),
                    ],
                    max_length=20,
                )),
                ('description', models.TextField(
                    help_text="Natural-language log entry, e.g. 'Patient had lunch at 2:30 pm'"
                )),
                ('details', models.JSONField(blank=True, default=dict)),
                ('observed_at', models.DateTimeField(
                    help_text='When the activity occurred (as reported/observed)'
                )),
                ('logged_at', models.DateTimeField(auto_now_add=True)),
                ('vitals_snapshot', models.JSONField(
                    blank=True,
                    default=dict,
                    help_text="Patient's most-recent vitals at the moment of logging",
                )),
                ('ai_confidence', models.CharField(
                    choices=[('HIGH', 'High'), ('MEDIUM', 'Medium'), ('LOW', 'Low')],
                    default='MEDIUM',
                    max_length=6,
                )),
                ('is_notable', models.BooleanField(
                    default=False,
                    help_text='AI flagged this as unusual or worth clinician attention',
                )),
                ('notable_reason', models.TextField(blank=True)),
                ('tags', models.JSONField(blank=True, default=list)),
                ('patient', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='activity_logs',
                    to='patients.patientprofile',
                )),
                ('session', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='activity_logs',
                    to='agent.agentsession',
                )),
            ],
            options={
                'db_table': 'patient_activity_logs',
                'ordering': ['-observed_at'],
            },
        ),
        migrations.AddIndex(
            model_name='patientactivitylog',
            index=models.Index(fields=['patient', '-observed_at'], name='pat_act_patient_obs_idx'),
        ),
        migrations.AddIndex(
            model_name='patientactivitylog',
            index=models.Index(fields=['activity_type', '-observed_at'], name='pat_act_type_obs_idx'),
        ),
        migrations.AddIndex(
            model_name='patientactivitylog',
            index=models.Index(fields=['is_notable', '-observed_at'], name='pat_act_notable_obs_idx'),
        ),
        migrations.AddIndex(
            model_name='patientactivitylog',
            index=models.Index(fields=['session'], name='pat_act_session_idx'),
        ),
    ]
