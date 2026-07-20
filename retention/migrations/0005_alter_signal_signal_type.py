from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('retention', '0004_attrition_forecast_and_history'),
    ]

    operations = [
        migrations.AlterField(
            model_name='signal',
            name='signal_type',
            field=models.CharField(choices=[('low_engagement', 'Low Engagement'), ('high_absence', 'High Absence Rate'), ('poor_performance', 'Poor Performance'), ('negative_feedback', 'Negative Feedback'), ('burnout_risk', 'Burnout Risk (workload)'), ('low_wellbeing', 'Low Wellbeing (self check-in)')], max_length=50),
        ),
    ]
