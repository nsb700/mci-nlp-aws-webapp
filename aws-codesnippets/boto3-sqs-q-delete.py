import boto3

sqs_client = boto3.client('sqs')
AWS_SQS_QUEUE = 'mcisqsqnsb700'

try:
    response = sqs_client.get_queue_url(QueueName = AWS_SQS_QUEUE)
    queue_url = response['QueueUrl']
    response = sqs_client.delete_queue(QueueUrl=queue_url)
    print('SQS queue %s deleted', AWS_SQS_QUEUE)
except sqs_client.exceptions.QueueDoesNotExist as e:
    print('SQS queue %s does not exist', AWS_SQS_QUEUE)
except Exception as e:
    raise e