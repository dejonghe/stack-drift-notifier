#!/usr/bin/env python3

import boto3
import json
import os
import re
from botocore.exceptions import ClientError
from datetime import datetime, timedelta, timezone
from itertools import repeat
from multiprocessing import Pool
from time import sleep

from decorators import retry
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

REGIONS = [
    'ap-south-1', 
    'eu-west-3', 
    'eu-west-2', 
    'eu-west-1', 
    'ap-northeast-2', 
    'ap-northeast-1', 
    'sa-east-1', 
    'ca-central-1', 
    'ap-southeast-1', 
    'ap-southeast-2', 
    'eu-central-1', 
    'us-east-1', 
    'us-east-2', 
    'us-west-1', 
    'us-west-2'
]

class DriftDetector(object):
    '''
    DriftDetector is a class that runs drift detection
    on every stack and sends an SNS push for any resource not in sync.

    Attributes:
        stacks  List of Stack Objects
    '''
    stacks = []
    failed_stack_ids = []

    def __init__(self,profile=None,region=None):
        self.sns_topic = os.environ.get('SNS_TOPIC_ID',None)
        self.sns_subject = os.environ.get('SNS_SUBJECT',"CFN Drift Detector Report")
        self.sns = SNSlogger(
                       self.sns_topic, 
                       self.sns_subject, 
                       profile=profile
                   )
        session = boto3.session.Session(
                      profile_name=profile,
                      region_name=region
                  )
        self.cfn_client = session.client('cloudformation')
        self.detections = self.check_drift()
        self.sns.log.info("Detections: {}".format(self.detections))
        self.wait_for_detection()
        self.report()


    def _get_stacks(self):
        '''
        Retreives all stacks in region
        '''
        resp = self._cfn_call('list_stacks',{'StackStatusFilter':ACTIVE_STACK_STATUS})
        stacks = resp['StackSummaries']
        while stacks == None or 'NextToken' in resp.keys():
            resp = self._cfn_call('list_stacks',{'NextToken':resp['NextToken']})
            stacks.append(resp['StackSummaries'])
        return stacks
        

    def check_drift(self,last_check_threshold=60):
        '''
        Checks every stack for drift
        '''
        detections = []
        for stack in self._get_stacks():
            resp = None
            check_threshold = datetime.now(timezone.utc) - timedelta(seconds=last_check_threshold)
            print('Stack: {}'.format(stack))
            if stack.get('DriftInformation', {'StackDriftStatus':'NOT_CHECKED'})['StackDriftStatus'] == 'NOT_CHECKED':
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
            resp = self._cfn_call('detect_stack_drift',{'StackName':stack_name})
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
                print('Checking {}'.format(detection_id))
                resp = self._cfn_call('describe_stack_drift_detection_status',{'StackDriftDetectionId':detection_id})
                detection_status = resp['DetectionStatus']
                if detection_status == 'DETECTION_IN_PROGRESS':
                    try_count += 1
                    sleep(backoff * try_count)
            # Detections fail if a resource is not supported but we want to know if there's a failure other than that.
            if detection_status == 'DETECTION_FAILED' and 'Failed to detect drift on resource' not in resp['DetectionStatusReason']:
                self.sns.log.critical('Detection Failed, StackId: {}, Reason: {}'.format(resp['StackId'],resp['DetectionStatusReason']))
                self.failed_stack_ids.append(resp['StackId'])

    def report(self):
        # report_obj = {}
        for stack in self._get_stacks():
            if stack['StackId'] not in self.failed_stack_ids:
                print('Stack result: {}'.format(stack))
                log_line = 'StackName: {}, DriftStatus: {}, LastCheckTimestamp: {}'.format(
                    stack['StackName'],
                    stack['DriftInformation']['StackDriftStatus'],
                    stack['DriftInformation']['LastCheckTimestamp']
                )
                if stack['DriftInformation']['StackDriftStatus'] == 'DRIFTED':
                    self.sns.log.critical(log_line)
                else:
                    self.sns.log.info(log_line)

            #report_obj[stack['StackName']] = {
            #    'DriftStatus': stack['DriftInformation']['StackDriftStatus'],
            #    'LastCheckTimestamp': stack['DriftInformation']['LastCheckTimestamp'].isoformat(timespec='minutes')
            #}
                   
    @retry(ClientError)
    def _cfn_call(self,method,parameters={}):
        '''
        Put a retry decorator on any cfn method to avoid rate limit
        '''
        return getattr(self.cfn_client,method)(**parameters)

def drift_region(profile,region):
    dd = DriftDetector(profile,region)
    return True
 
def lambda_handler(event,context):
    if isinstance(context,test_context):
        profile = context.profile
        regions = REGIONS if context.region == 'all' else [context.region]
    else:
        profile = None
        regions = os.environ.get('REGIONS',REGIONS)
    with Pool(len(regions)) as p:
        p.starmap(drift_region,zip(repeat(profile),regions))


class test_context(dict):
    '''This is a text context object used when running function locally'''
    def __init__(self,profile,region=None):
        self.profile = profile
        self.region = region

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Lambda Function that detects CloudFormation drift.')
    parser.add_argument("-r","--region", help="Region in which to run. Default: all (will run for all regions)", default='all')
    parser.add_argument("-p","--profile", help="Profile name to use when connecting to aws.", default=None)

    args = parser.parse_args()

    event = {}   
    context = test_context(args.profile,args.region)

    lambda_handler(event,context)
