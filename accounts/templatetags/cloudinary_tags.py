import os
from django import template

register = template.Library()

@register.filter
def cloudinary_url(public_id):
    """Generate Cloudinary URL from a public_id stored in ImageField."""
    if not public_id:
        return ''
    cloud_name = os.getenv('CLOUDINARY_CLOUD_NAME', '')
    if not cloud_name:
        return ''
    # Handle if public_id is a FieldFile object (has .name attribute)
    if hasattr(public_id, 'name'):
        public_id = public_id.name
    return f'https://res.cloudinary.com/{cloud_name}/image/upload/{public_id}'


@register.filter
def file_url(file_field):
    """Generate proper URL for file uploads - Cloudinary in production, local in development."""
    if not file_field:
        return ''
    
    # First try to get URL from storage backend (works for both Cloudinary and local)
    if hasattr(file_field, 'url'):
        url = file_field.url
        # If it's already a full URL, use it
        if url and url.startswith('http'):
            return url
    
    # Fallback: construct Cloudinary URL manually
    cloud_name = os.getenv('CLOUDINARY_CLOUD_NAME', '')
    if cloud_name:
        name = file_field.name if hasattr(file_field, 'name') else str(file_field)
        # Try image/upload for images (most common)
        return f'https://res.cloudinary.com/{cloud_name}/image/upload/v1/{name}'
    
    # Local development fallback
    return file_field.url if hasattr(file_field, 'url') else ''
