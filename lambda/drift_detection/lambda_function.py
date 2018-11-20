#!/usr/bin/env python3

import boto3
import os
import re
from botocore.exceptions import ClientError
from datetime import datetime, timedelta, timezone
from time import sleep

from sns_logger import SNSlogger


ACTIVE_STACK_STATUS=[
    'CREATE_IN_PROGRESS',
    'CREATE_FAILED',
    'CREATE_COMPLETE',
    'ROLLBACK_IN_PROGRESS',
    'ROLLBACK_FAILED',
    'ROLLBACK_COMPLETE',
    'UPDATE_IN_PROGRESS',
    'UPDATE_COMPLETE_CLEANUP_IN_PROGRESS',
    'UPDATE_COMPLETE',
    'UPDATE_ROLLBACK_IN_PROGRESS',
    'UPDATE_ROLLBACK_FAILED',
    'UPDATE_ROLLBACK_COMPLETE_CLEANUP_IN_PROGRESS',
    'UPDATE_ROLLBACK_COMPLETE',
    'REVIEW_IN_PROGRESS'
]

class DriftDetector(object):
    '''
    DriftDetector is a class that runs drift detection
    on every stack and sends an SNS push for any resource not in sync.

    Attributes:
        stacks  List of Stack Objects
    '''
    stacks = []

    def __init__(self,profile=None,region=None):
        self.sns_topic = os.environ.get('sns_topic_id',None)
        self.sns_subject = os.environ.get('sns_subject',"CFN Drift Detector Report")
        self.sns = SNSlogger(
                       self.sns_topic, 
                       self.sns_subject, 
                       profile=profile,
                       region=region
                   )
        session = boto3.session.Session(
                      profile_name=context.profile,
                      region_name=context.region
                  )
        self.cfn_client = session.client('cloudformation')
        self.stacks = self._get_stacks()
        self.detections = self.check_drift()
        self.sns.log.info("Detections: {}".format(self.detections))
        self.wait_for_detection()


    def _get_stacks(self):
        '''
        Retreives all stacks in region
        '''
        resp = self.cfn_client.list_stacks(StackStatusFilter=ACTIVE_STACK_STATUS)
        stacks = resp['StackSummaries']
        while stacks == None or 'NextToken' in resp.keys():
            resp = self.cfn_client.list_stacks(NextToken=resp['NextToken'])
            stacks.append(resp['StackSummaries'])
        return stacks
        

    def check_drift(self,last_check_threshold=60):
        '''
        Checks every stack for drift
        '''
        detections = []
        for stack in self.stacks:
            resp = None
            check_threshold = datetime.now(timezone.utc) - timedelta(seconds=last_check_threshold)
            if stack['DriftInformation']['StackDriftStatus'] == 'NOT_CHECKED':
                resp = self._detect(stack['StackName'])
            else:
                if stack['DriftInformation']['LastCheckTimestamp'] < check_threshold:
                    resp = self._detect(stack['StackName'])
            if resp:
                detections.append(resp)
        return detections


    def _detect(self,stack_name):
        '''
        Private method for making the detect request with exception handling
        '''
        # I really wish there was a list drift operations and status so this was not necessay
        try:
            resp = self.cfn_client.detect_stack_drift(StackName=stack_name)
            return resp['StackDriftDetectionId']
        except ClientError as e:
            if 'Drift detection is already in progress for stack' in e.response['Error']['Message']:
                self.log.critical(e.response['Error']['Message'])
            return None

    def wait_for_detection(self,backoff=3,max_tries=3):
        for detection_id in self.detections:
            try_count = 0
            detection_status = 'DETECTION_IN_PROGRESS'
            while detection_status == 'DETECTION_IN_PROGRESS' and try_count <= max_tries:
                resp = self.cfn_client.describe_stack_drift_detection_status(StackDriftDetectionId=detection_id)
                detection_status = resp['DetectionStatus']
                if detection_status == 'DETECTION_IN_PROGRESS':
                    try_count += 1
                    sleep(backoff * try_count)
                   
                    
 
def lambda_handler(event,context):
    if isinstance(context,test_context):
        profile = context.profile
        region = context.region 
    else:
        profile = None
        region = None
    dd = DriftDetector(profile,region)
    #sleep(60)
    return True


class test_context(dict):
    '''This is a text context object used when running function locally'''
    def __init__(self,profile,region=None):
        self.profile = profile
        self.region = region

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Lambda Function that detects CloudFormation drift.')
    parser.add_argument("-r","--region", help="Region in which to run.", default=None)
    parser.add_argument("-p","--profile", help="Profile name to use when connecting to aws.", default=None)

    args = parser.parse_args()

    event = {}   
    context = test_context(args.profile,args.region)

    lambda_handler(event,context)
