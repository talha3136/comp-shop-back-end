from django.db.models.signals import post_delete, pre_save
from django.dispatch import receiver
from django.db import models

def delete_file_from_storage(file_field):
    """Deletes a file from storage if it exists."""
    if file_field and hasattr(file_field, 'storage'):
        storage = file_field.storage
        path = file_field.name
        if path and storage.exists(path):
            storage.delete(path)

@receiver(post_delete)
def auto_delete_file_on_delete(sender, instance, **kwargs):
    """
    Deletes file from storage
    when corresponding object is deleted.
    """
    # Check all fields in the model
    for field in instance._meta.fields:
        if isinstance(field, (models.FileField, models.ImageField)):
            file_field = getattr(instance, field.name)
            if file_field:
                delete_file_from_storage(file_field)

@receiver(pre_save)
def auto_delete_file_on_change(sender, instance, **kwargs):
    """
    Deletes old file from storage
    when corresponding object is updated
    with a new file.
    """
    if not instance.pk:
        return

    try:
        old_instance = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return

    for field in instance._meta.fields:
        if isinstance(field, (models.FileField, models.ImageField)):
            new_file = getattr(instance, field.name)
            old_file = getattr(old_instance, field.name)
            
            # If the file has changed, delete the old one
            if old_file and new_file != old_file:
                # Be careful not to delete if the filename is the same 
                # (though Django usually appends suffixes if not overwriting)
                delete_file_from_storage(old_file)
