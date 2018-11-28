# CloudFormation Stack Drift Notifier

## Overview
The purpose of this project to setup a lambda that runs on a schedule to detect CloudFormation drift. The lambda runs on a schedule specified by a parameter passed to the CloudFormation stack that sets up the project. By default, the lambda will check every region in parallel. A SNS notification is sent to the subscribing email address for every stack that has drifted. 

## Quick Setup
I host the lambda and the CloudFormation from a public bucket. You can launch it directly from this button. The lambda function package is distributed to a bucket in each region, which means that you can launch this template into any region you wish.

[![CloudFormation Link](https://s3.amazonaws.com/cloudformation-examples/cloudformation-launch-stack.png)](https://console.aws.amazon.com/cloudformation/home#/stacks/new?stackName=Stack-Drift-Notifier&templateURL=https://s3.amazonaws.com/stack-drift-notifier/master/cloudformation/drift_detection.yaml)

## Manual Set up Drift Detector 
Before you deploy this CloudFormation template, you need to build the lambda function into a zip and host it on S3. 

### Assumptions:
* You have an AWS Account.
* You’re using Bash.
* You have git installed.
* You have pip installed. [Help](https://pip.pypa.io/en/stable/installing/)
* You have the AWS CLI installed, preferred version 1.16.54 or greater. [Help](https://docs.aws.amazon.com/cli/latest/userguide/installing.html)
* You have configured the CLI, set up AWS IAM access credentials that have appropreate access. [Help](https://docs.aws.amazon.com/cli/latest/reference/configure/index.html)

### Step 1: Clone the example Github project.
I have prepared a Github project with all of the example CloudFormation and code to get you off the ground. Clone this Github project to your local machine.

```
git clone https://github.com/dejonghe/stack-drift-notifier
```

### Step 2: Create a S3 Bucket. (Skip if you have a bucket to work from, use that buckets name from now on)
You will need a S3 bucket to work out of, we will use this bucket to upload our lambda code zip. Create the bucket with the following CLI command or through the console. Keep in mind that S3 bucket names are globally unique and you will have to come up with a bucket name for yourself.
```
aws s3 mb s3://drift_detector_{yourUniqueId} (--profile optionalProfile)
```

### Step 3: Run the env_prep Script.
To prepare
You must run a script from within the Github project. This script is to be ran from the base of the repository. If you rename the repository directory you will need to edit the [script](./bin/env_prep.sh), all the variables are at the top.

This script performs the following tasks:
1. Builds and and uploads the lambda code
  * The script creates a temp directory
  * Copies the code from [lambda/drift_detection](./lambda/drift_detection/) to the temp directory
  * Uses pip to install the requirements to the temp directory
  * Zips up the contents of the temp directory to a package named ./lambda/drift_detection.zip
  * Removes the temp directory
  * Uploads the zip to `s3://{yourBucket}/{release(master)}/lambda/drift_detection.zip`
The following is an example of running the script. **Note:** You can pass -p profile, and -r release (Your aws-cli profile's default regions is used)
```
./bin/env_prep.sh -b drift_detector_{yourUniqueId} (-p optionalProfile -r optionalRelease)
```

### Step 4: Create the CloudFormation Stack.
This step utilizes the [CloudFormation Tempalte](./cloudformation/drift_detection.yaml) to produce a number of resources that runs drift detection on a schedule. The template creates a IAM role for lambda to assume, a policy to go with it, a SNS topic to notify if a stack has drifted, the lambda function, a CloudWatch schedule, and permission for the schedule to invoke the lambda. 

There are a number of optional parameters, check the template if you wish to alter the default configuration.
```
aws cloudformation create-stack --template-body file://cloudformation/drift_detection.yaml --stack-name drift-detection --parameters '[{"ParameterKey":"NotifyEmail","ParameterValue":"EmailAddressToNotify"},{"ParameterKey":"LambdaS3Bucket","ParameterValue":"drift_detector_{yourUniqueId}"}]' --capabilities CAPABILITY_NAMED_IAM (--profile optionalProfile)
```
Wait for the CloudFormation stack to complete. With the default configuration drift detection will run daily. 
