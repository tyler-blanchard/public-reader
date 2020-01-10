import logging
import os
import boto3
from botocore.exceptions import ClientError
import urllib.request
from lxml import etree
from epub_parser import Epub
import shutil
import zipfile
import re
import math

def query(keywords):
    """ Uses standardebooks.org query function

    :param keywords: string
    :return: search results
    """
    
    # url
    base_url = 'https://standardebooks.org/ebooks/?query='
    query = re.sub(' ', '+', keywords)
    url = base_url + query
    
    # html 
    http = urllib.request.urlopen(url)
    html = http.read().decode('utf-8')
    parser = etree.HTMLParser()
    tree = etree.fromstring(html, parser=parser)
    
    try:
        items = tree.xpath('body/main/ol/li')
    except: 
        return []
    
    # build result
    search_result = []
    
    for item in items:
        p_tags = item.xpath('p')
        
        title = p_tags[0]
        title_link = title.xpath('a/@href')[0]
        title_label = title.xpath('a/text()')[0]
        
        author = p_tags[1]
        author_link = author.xpath('a/@href')[0]
        author_label = author.xpath('a/text()')[0]
        
        search_item = {
            'title': title_label,
            'titleLink': title_link,
            'author': author_label,
            'authorLink': author_link
        }
        
        search_result.append(search_item)
        
    return search_result

def open_book(titleLink):
    """ Downloads standardebooks.org epub file
    
    :param titleLink: string
    :return: epub object
    """
    
    base_url = 'https://standardebooks.org'
    
    url = base_url + titleLink
    
    http = urllib.request.urlopen(url)
    html = http.read().decode('utf-8')
    
    parser = etree.HTMLParser()
    
    # parse for download link
    tree = etree.fromstring(html, parser=parser)
    epub_link = tree.xpath('//section[@id = "download"]/ul/li/p/span/a/@href')[0]
    epub_url = base_url + epub_link
    
    path = '/tmp/out.zip'
    
    # download and copy file to tmp/out.zip
    
    with open(path, 'wb') as out_file:
        
        response = urllib.request.urlopen(epub_url)
        
        shutil.copyfileobj(response, out_file)
        
    return open_zipped_epub()


def open_zipped_epub():
    """ Opens epub in tmp/out.zip 
    
    :return: epub object
    """
    
    path = '/tmp/out.zip'

    epub_zip = zipfile.ZipFile(path)
    
    epub = Epub(epub_zip)
    
    return epub

def read_chapter(handler_input, chapter):
    
    """ Generates an alexa response based on chapter text

    :param handler_input: alexa input
    :param chapter: chapter dictionary object
    :return: alexa response
    """
    
    # when chapter couldn't be found
    if chapter == None:
        
        speak_output = 'Sorry, I had trouble finding that text. Please try again.'
        
        return (
            handler_input.response_builder
                .speak(speak_output)
                .set_should_end_session(False)
                .response
        )
        
    # assign bookmark
    session_attr = handler_input.attributes_manager.session_attributes
    
    file = chapter['file']
    section = chapter['section']
    
    session_attr["bookmark"] = {
        'file': file,
        'section': section
    }
    
    # speaker output text
    if 'title' in chapter:
        speak_output = 'Reading: ' + chapter['title'] + '<break time="1s"/> ' + chapter['text']
    else:
        speak_output = chapter['text']
       
    # reprompt 
    reprompt = "Say 'next' and I will continue reading."
    
    return (
        handler_input.response_builder
            .speak(speak_output)
            .ask(reprompt)
            .set_should_end_session(False)
            .response
    )


def create_presigned_url(object_name):
    """ Generate a presigned URL to share an S3 object with a capped expiration of 60 seconds

    :param object_name: string
    :return: Presigned URL as string. If error, returns None.
    """
    s3_client = boto3.client('s3', config=boto3.session.Config(signature_version='s3v4',s3={'addressing_style': 'path'}))
    try:
        bucket_name = os.environ.get('S3_PERSISTENCE_BUCKET')
        response = s3_client.generate_presigned_url('get_object',
                                                    Params={'Bucket': bucket_name,
                                                            'Key': object_name},
                                                    ExpiresIn=60*1)
    except ClientError as e:
        logging.error(e)
        return None

    # The response contains the presigned URL
    return response