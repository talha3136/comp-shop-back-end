from storages.backends.s3boto3 import S3Boto3Storage

class R2MediaStorage(S3Boto3Storage):
    bucket_name = "mobicloud"  # optional if set in settings
    custom_domain = False  # important for correct URLs

    def delete(self, name):
        if self.exists(name):
            super().delete(name)

    def save(self, name, content, max_length=None):
        if self.exists(name):
            self.delete(name)
        return super().save(name, content, max_length)
