import boto3
import logging
import re

class SNSLogHandler(logging.Handler):
    def __init__(self, topic, subject, profile=None):
        logging.Handler.__init__(self)
        region = re.search('arn:\w+:\w+:(.+?):\d+:.+$', topic).group(1)
        self.session = boto3.session.Session(profile_name=profile,region_name=region)
        self.sns_client = self.session.client('sns')
        self.topic = topic
        self.subject = subject

    def emit(self, record):
        self.sns_client.publish(TopicArn=self.topic, Message=record.message, Subject=self.subject)

class SNSlogger(object):
    def __init__(self, sns_topic_id, sns_topic_subject, profile=None):
        self.sns_topic = sns_topic_id
        self.sns_subject = sns_topic_subject
        self.profile = profile
        self._init_logging()

    def _init_logging(self):
        self.log = logging.getLogger('SNS_Logger')

        # Should set the level on the logger itself to DEBUG
        # and let the handlers below do the filtering 
        self.log.setLevel(logging.DEBUG)
        # Setting console output to DEBUG for easier debugging
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        # THIS NEEDS TO BE CHANGED.
        hdlr = logging.FileHandler('/tmp/sns.log')
        hdlr.setFormatter(formatter)
        ch.setFormatter(formatter)
        self.log.addHandler(ch)
        self.log.addHandler(hdlr)
        sns = SNSLogHandler(self.sns_topic, self.sns_subject, self.profile)

        # We only want critical messages bothering us via AWS SNS
        sns.setLevel(logging.CRITICAL)
        sns.setFormatter(formatter)
        self.log.addHandler(sns)
