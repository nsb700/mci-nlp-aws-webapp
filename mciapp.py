from fastapi import FastAPI, UploadFile, HTTPException, status, Response
from pathlib import Path
import magic
import boto3
from botocore.exceptions import ClientError
import logging
from logging import config
import msiconstants
import json
from PyPDF2 import PdfReader
from pdf2image import convert_from_bytes
import pytesseract
from io import BytesIO
import re
import pandas as pd
from sentence_transformers import SentenceTransformer, util
import torch
import itertools
from wordcloud import WordCloud

config.dictConfig(msiconstants.LOG_CONFIG)
logger = logging.getLogger(__name__)
pytesseract.pytesseract.tesseract_cmd = r'/usr/bin/tesseract' 

def getIcdDict(filename: str):
    df = pd.read_csv(filename)
    df_dict = df.to_dict()
    code_to_index_dict = dict(zip(df['icdcode'], df.index))
    icdcodeslist = df['icdcode'].to_list()
    return df_dict, code_to_index_dict, icdcodeslist

df_dict, code_to_index_dict, icdcodeslist = getIcdDict('transformed_codesfile.csv')

model = SentenceTransformer(model_name_or_path = msiconstants.MODEL_NAME)
codes_file_embeddings = torch.load(f='tensor.pt', map_location='cpu')
s3_resource = boto3.resource('s3')
s3_bucket_fileadd = s3_resource.Bucket(msiconstants.AWS_BUCKET_FILEADD)
s3_bucket_nlpres = s3_resource.Bucket(msiconstants.AWS_BUCKET_NLPRES)
sqs_client = boto3.client('sqs')
s3_client = boto3.client('s3')

async def s3_upload(contents: bytes, key: str):
    logger.info('Uploading %s to s3', key)
    s3_bucket_fileadd.put_object(Key=key, Body=contents)

async def s3_download(key: str):
    logger.info('Downloading %s from s3', key)
    try:
        return s3_resource.Object(bucket_name=msiconstants.AWS_BUCKET_NLPRES, key=key).get()['Body'].read()
    except ClientError as err:
        logger.error(str(err))


async def s3_and_sqs_objs_delete():
    logger.info('Deleting all objects from s3')
    s3_bucket_fileadd.objects.all().delete()
    s3_bucket_nlpres.objects.all().delete()
    response = sqs_client.get_queue_url(QueueName = msiconstants.AWS_SQS_QUEUE)
    sqs_client.purge_queue(QueueUrl=response['QueueUrl'])


app = FastAPI()

#==========
# ROOT PATH
#==========
@app.get("/")
async def root():
    return {'message': 'Welcome to Medical Charts Indexer'}


#================================
# UPLOAD FILE
# Only pdf files upto 2MB in size
#================================
@app.post("/upload")
async def upload(file: UploadFile):
    if not file:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='No file found!'
        )
    contents = await file.read()
    file_size = len(contents)
    if not 0 < file_size < (msiconstants.MAX_SIZE_IN_MB * msiconstants.MB):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f'Supported file size 0 - {msiconstants.MAX_SIZE_IN_MB * msiconstants.MB} MB'
        )
    file_type = magic.from_buffer(buffer=contents, mime=True)
    if file_type not in msiconstants.SUPPORTED_FILE_TYPES:
        supported_file_types = msiconstants.SUPPORTED_FILE_TYPES.keys()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f'Unsupported file type: {file_type}. Supported file types are {supported_file_types}'
        )
    await s3_upload(contents=contents, key=f'{Path(file.filename).stem}.{msiconstants.SUPPORTED_FILE_TYPES[file_type]}')


#=====================================
# DELETE OBJECTS FROM BUCKETS & QUEUE
#=====================================
@app.post("/delete")
async def delete():
    await s3_and_sqs_objs_delete()

#==========================================
# CLEAN PAGE TEXT (remove punctuations etc)
#==========================================
def clean_page_text(page_text: str):
    page_text_lines = []
    page_text = page_text.lower()
    linearr = page_text.split('\n')
    for line in linearr:
        x = re.sub(r'[^\w\s]', '', line.strip())
        if len(x) > 0:
            page_text_lines.append(x)    
    return '\n'.join(page_text_lines)


#=========================================================================
# FIND NLP MATCH OF EACH LINE WITH EACH OF 11,252 DIAGNOSIS CODES & LABELS
# Refer https://www.sbert.net/
#=========================================================================
def nlp_process(key, page_number, page_text_lines_string):
    logger.info('Start nlp - chart: %s , page: %s', key, page_number)
    page_text_lines = page_text_lines_string.split('\n')
    page_text_embeddings = model.encode(page_text_lines, convert_to_tensor=True, normalize_embeddings=True)
    res = []
    # Check for cosine similarity
    cosine_scores = util.dot_score(codes_file_embeddings, page_text_embeddings)
    idx = torch.nonzero(cosine_scores > msiconstants.THRESHOLD)
    for i in range(idx.shape[0]):
        idx_of_icdcode = idx[i][0].item()
        idx_of_pdftext = idx[i][1].item()
        diagcodelvl1 = df_dict['diagcodelvl1'][idx_of_icdcode]
        diagdesclvl1 = df_dict['diagdesclvl1'][idx_of_icdcode]
        ln = f"{key},{page_number},{diagcodelvl1},{diagdesclvl1},{page_text_lines[idx_of_pdftext]}"
        res.append(ln)
    # Check if icdcode in pdftext
    crossprod = list(itertools.product(icdcodeslist, page_text_lines))
    code_in_text = [(pair[0], pair[1]) for pair in crossprod if pair[0] in pair[1]]
    for icdcode, pdftext in code_in_text:
        idx_of_icdcode = code_to_index_dict[icdcode]
        diagcodelvl1 = df_dict['diagcodelvl1'][idx_of_icdcode]
        diagdesclvl1 = df_dict['diagdesclvl1'][idx_of_icdcode]
        ln = f"{key},{page_number},{diagcodelvl1},{diagdesclvl1},{pdftext}"
        res.append(ln)
    if len(res) > 0:
        res = list(set(res))
        logger.info('End nlp - chart: %s , page: %s', key, page_number)
    return res


#=============
# PROCESS FILE
#=============
@app.post("/processfile")
async def processfile():
    response = sqs_client.get_queue_url(QueueName = msiconstants.AWS_SQS_QUEUE)
    queueUrl = response['QueueUrl']
    response = sqs_client.receive_message(QueueUrl=queueUrl, MaxNumberOfMessages=1)
    message = json.loads(response["Messages"][0]["Body"])
    key = message["Key"]
    for obj in s3_bucket_fileadd.objects.all():
        if obj.key == key:  
            body = obj.get()['Body'].read()
            try:
                reader = PdfReader(BytesIO(body))
            except:
                logger.info('Bad file: %s',key)
                return {'message': 'Bad file'}
            pages = reader.pages
            page_count = len(pages)
            first_page = pages[0]
            first_page_text = first_page.extract_text()
            page_text = ''
            file_nlp_res = ['chart,page_number,diagcodeLvl1,diagdescLvl1,pdftext']
            if len(first_page_text) <= 2:
                logger.info('Good scanned file: %s', key)
                imgs = convert_from_bytes(BytesIO(body))
                for i in range(len(imgs)):
                    page_text = pytesseract.image_to_string(imgs[i])
                    page_text_lines = clean_page_text(page_text)
                    res = nlp_process(key, i, page_text_lines)
                    if len(res) > 0:
                        file_nlp_res.extend(res)
            else:
                logger.info('Good regular file: %s', key)
                for i in range(len(pages)):
                    page_text = pages[i].extract_text()
                    page_text_lines = clean_page_text(page_text)
                    res = nlp_process(key, i, page_text_lines)
                    if len(res) > 0:
                        file_nlp_res.extend(res)
            nlp_result_key = f'{Path(key).stem}.txt'
            resultBody = '\n'.join(file_nlp_res)
            s3_resource.Object(msiconstants.AWS_BUCKET_NLPRES, nlp_result_key).put(Body=resultBody)
            sqs_client.purge_queue(QueueUrl=queueUrl)
            return {'nlpresultfilename': nlp_result_key}


#=================
# CREATE WORDCLOUD
#=================
@app.get("/createwordcloud")
async def createwordcloud(filename: str | None = None):
    if not filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f'No NLP result file'
        )
    for obj in s3_bucket_nlpres.objects.all():
        if obj.key == filename:  
            body = obj.get()['Body'].read()
            df = pd.read_csv(BytesIO(body))
            wordcloud = WordCloud(background_color="white", scale=1.5).generate(' '.join(list(df['diagdescLvl1'].unique())))
            wordcloudfilename = f'{Path(filename).stem}.png'
            wordcloud.to_file(wordcloudfilename)
            s3_client.upload_file(wordcloudfilename, msiconstants.AWS_BUCKET_NLPRES, wordcloudfilename)
            Path(wordcloudfilename).unlink()
            return {'wordcloudfilename': wordcloudfilename}


#=====================
# DOWNLOAD RESULT FILE
#=====================
@app.get("/downloadnlpresult")
async def downloadnlpresult(filename: str | None = None):
    if not filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f'No NLP result file'
        )
    contents = await s3_download(key=filename)
    return Response(
        content = contents,
        headers = {
            'Content-Disposition': f'attachment;filename={filename}',
            'Content-Type': 'application/octet-stream',   
        }
    )