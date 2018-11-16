#!/usr/bin/env python3

import boto3
import re
from botocore.exceptions import ClientError
from datetime import datetime, timedelta, timezone
from time import sleep

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

    def __init__(self,event,context):
        session = self._setup_session(context)
        self.cfn_client = session.client('cloudformation')
        self.stacks = self._get_stacks()
        self.detections = self.check_drift()

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
        
    def _setup_session(self,context):
        '''
        Checks to see if running locally by use of test_context
        If so use profile and region from test_context
        If not use default session
        '''
        if isinstance(context,test_context):
            # For testing use profile and region from test_context
            print('Using test_context')
            print("Profile: {}".format(context.profile))
            print("Region: {}".format(context.region))
            self.test = True
            return boto3.session.Session(profile_name=context.profile,region_name=context.region)
        else:
            # Sets up the session in lambda context
            return boto3.session.Session()

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
        # I really wish there was a list drift operations so this was not necessay
        try:
            resp = self.cfn_client.detect_stack_drift(StackName=stack_name)
            return resp['StackDriftDetectionId']
        except ClientError as e:
            if 'Drift detection is already in progress for stack' in e.response['Error']['Message']:
                print(e.response['Error']['Message'])
            return None

    def wait_for_detection(self):
        pass
 
def lambda_handler(event,context):
    dd = DriftDetector(event,context)
    print(dd.detections)
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
