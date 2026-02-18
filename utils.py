from functools import wraps
from django.utils import timezone
from django.conf import settings




def append_datetime_to_filepath(func):
    @wraps(func)
    def wrapper(instance, filename):
        # Get current datetime in the specified format
        current_datetime = timezone.now().strftime('%Y%m%d%H%M%S')
        
        # Get the original filepath
        filepath = func(instance, filename)
        
        # Insert the datetime as a subfolder before the filename
        directory, filename = filepath.rsplit('/', 1)
        updated_filepath = f'{directory}/{current_datetime}/{filename}'
        
        return updated_filepath
    
    return wrapper

@append_datetime_to_filepath
def user_profile_image_path(instance, filename):
    """Generate file path for user profile images."""
    return f'user_profiles/{instance.id}/{filename}'

@append_datetime_to_filepath
def customer_profile_image_path(instance, filename):
    """Generate file path for customer profile images."""
    return f'customer_profiles/{instance.shop.id}/{instance.id}/{filename}'

@append_datetime_to_filepath
def computer_purchase_photo_path(instance, filename):
    """Generate file path for computer purchase photos."""
    return f'computer_purchases/{instance.shop.id}/{instance.id}/{filename}'

@append_datetime_to_filepath
def computer_image_path(instance, filename):
    """Generate file path for computer images."""
    return f'computer_images/{instance.shop.id}/{instance.computer_purchase.id}/{filename}'

@append_datetime_to_filepath
def mobile_purchase_photo_path(instance, filename):
    """Generate file path for mobile purchase photos."""
    return f'mobile_purchases/{instance.shop.id}/{instance.id}/{filename}'

@append_datetime_to_filepath
def mobile_image_path(instance, filename):
    """Generate file path for mobile images."""
    return f'mobile_images/{instance.shop.id}/{instance.mobile_purchase.id}/{filename}'
