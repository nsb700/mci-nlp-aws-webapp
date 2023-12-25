import json
import boto3

sqs_client = boto3.client('sqs')
AWS_SQS_QUEUE = 'mcisqsqnsb700'

def lambda_handler(event, context):
    key = event['Records'][0]['s3']['object']['key']
    message = {"Key": key}
    response = sqs_client.get_queue_url(QueueName = AWS_SQS_QUEUE)
    queue_url = response['QueueUrl']
    response = sqs_client.send_message(QueueUrl=queue_url, MessageBody=json.dumps(message))
    return {
        "statusCode": 200, 
        "body": json.dumps(message),
    }
