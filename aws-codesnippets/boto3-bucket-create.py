import boto3

s3_client = boto3.client('s3')
AWS_BUCKET_FILEADD = 'mcis3fladdnsb700'

try:
    response = s3_client.get_bucket_location(Bucket = AWS_BUCKET_FILEADD)
    print('Bucket %s exists', AWS_BUCKET_FILEADD)
except s3_client.exceptions.NoSuchBucket as e:
    response = s3_client.create_bucket(Bucket = AWS_BUCKET_FILEADD)
    print('Created bucket %s', AWS_BUCKET_FILEADD)
except Exception as e:
    raise e