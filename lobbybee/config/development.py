from .base import *

# Development-specific settings
AWS_ACCESS_KEY_ID = env('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = env('AWS_SECRET_ACCESS_KEY')
AWS_STORAGE_BUCKET_NAME = env('AWS_STORAGE_BUCKET_NAME')
AWS_S3_REGION_NAME = env('AWS_DEFAULT_REGION')

# S3 File Storage Settings
AWS_DEFAULT_ACL = env('AWS_DEFAULT_ACL', default=None)
AWS_S3_OBJECT_PARAMETERS = env.dict('AWS_S3_OBJECT_PARAMETERS', default={
    'CacheControl': 'max-age=86400',
})
AWS_S3_FILE_OVERWRITE = env.bool('AWS_S3_FILE_OVERWRITE', default=False)
AWS_QUERYSTRING_AUTH = env.bool('AWS_QUERYSTRING_AUTH', default=True)
AWS_QUERYSTRING_EXPIRE = env.int('AWS_QUERYSTRING_EXPIRE', default=3600)

# Use S3 for file uploads only
DEFAULT_FILE_STORAGE = env('DEFAULT_FILE_STORAGE', default='lobbybee.utils.storage_backends.MediaStorage')

# File Upload Settings
FILE_UPLOAD_MAX_MEMORY_SIZE = env.int('FILE_UPLOAD_MAX_MEMORY_SIZE', default=5242880) # 5MB
DATA_UPLOAD_MAX_MEMORY_SIZE = env.int('DATA_UPLOAD_MAX_MEMORY_SIZE', default=5242880)   # 5MB
