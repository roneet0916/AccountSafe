from django.db import migrations, models


def invalidate_plaintext_pins(apps, schema_editor):
    """
    Clear all existing plaintext PINs since they cannot be verified
    against hashed values. Users will need to re-set their PINs.
    """
    UserProfile = apps.get_model('api', 'UserProfile')
    UserProfile.objects.filter(security_pin_hash__isnull=False).update(security_pin_hash=None)


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0038_storage_quota'),
    ]

    operations = [
        # Step 1: Rename the field from security_pin to security_pin_hash
        migrations.RenameField(
            model_name='userprofile',
            old_name='security_pin',
            new_name='security_pin_hash',
        ),
        # Step 2: Increase max_length to accommodate Django's password hash format
        migrations.AlterField(
            model_name='userprofile',
            name='security_pin_hash',
            field=models.CharField(
                blank=True,
                help_text='Hashed security PIN for accessing organizations (never stored in plaintext)',
                max_length=128,
                null=True,
            ),
        ),
        # Step 3: Invalidate all existing plaintext PINs
        migrations.RunPython(
            invalidate_plaintext_pins,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
