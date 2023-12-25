import boto3

sqs_client = boto3.client('sqs')
AWS_SQS_QUEUE = 'mcisqsqnsb700'

try:
    response = sqs_client.get_queue_url(QueueName = AWS_SQS_QUEUE)
    print('SQS queue %s exists', AWS_SQS_QUEUE)
except sqs_client.exceptions.QueueDoesNotExist as e:
    response = sqs_client.create_queue(QueueName = AWS_SQS_QUEUE)
    print('Created SQS queue %s', AWS_SQS_QUEUE)
except Exception as e:
    raise e