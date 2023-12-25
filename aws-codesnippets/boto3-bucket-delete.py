import boto3

s3_resource = boto3.resource('s3')
s3_client = boto3.client('s3')
AWS_BUCKET_FILEADD = 'mcis3fladdnsb700'

try:
    s3_bucket = s3_resource.Bucket(AWS_BUCKET_FILEADD)
    s3_bucket.objects.all().delete()
    response = s3_client.delete_bucket(Bucket = AWS_BUCKET_FILEADD)
    print('Bucket %s deleted', AWS_BUCKET_FILEADD)
except s3_client.exceptions.NoSuchBucket as e:
    print('Bucket %s does not exist.', AWS_BUCKET_FILEADD)
except Exception as e:
    raise e