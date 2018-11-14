#!/usr/bin/env python3

import boto3

class DriftDetector(object):
    '''
    DriftDetector is a class that runs drift detection
    on every stack and sends an SNS push for any resource not in sync.

    Attributes:
        stacks  List of StackNames
    '''
    stacks = []

    def __init__(self,event,context):
        session = self._setup_session(context)
        self.cfn_client = session.client('cloudformation')
        self.stacks = self._get_stacks()

    def _get_stacks(self):
        '''
        Retreives all stacks in region
        '''
        resp = self.cfn_client.list_stacks()
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

 
def lambda_handler(event,context):
    dd = DriftDetector(event,context)
    print(dd.stacks)

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
