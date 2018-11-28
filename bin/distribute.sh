#!/bin/bash

set -e
# Set variables
logfile=distribute.log
base_home_dir=stack-drift-notifier
lambda_code_path=lambda
lambda_func_name=drift_detection
lambda_pkg_name=${lambda_func_name}.zip

# Define Usage
function usage()
{
  echo "Usage: $0 {args}"
  echo "Where valid args are: "
  echo "  -p <profile> -- Profile to use for AWS commands, defaults to 'default'"
  echo "  -r <release> -- Release variable used for bucket path, defaults to 'develop'"
  exit 1
}

# Parse args
if [[ "$#" -lt 2 ]] ; then
  echo 'parse error'
  usage
fi
PROFILE=default
RELEASE=master
while getopts "p:r:b:" opt; do
  case $opt in
    p)
      PROFILE=$OPTARG
    ;;
    r)
      RELEASE=$OPTARG
    ;;
    \?)
      echo "Invalid option: -$OPTARG"
      usage
    ;;
  esac
done

# Makes sure you're in the right directory
CWD=$(echo $PWD | rev | cut -d'/' -f1 | rev)
if [ $CWD != ${base_home_dir} ]
then
  echo "These tools are expecting to be ran from the base of the drift_detection repo. If you edited the name of the directory edit the env_prep.sh script."
  exit 1
fi

for region in ap-south-1 eu-west-3 eu-west-2 eu-west-1 ap-northeast-2 ap-northeast-1 sa-east-1 ca-central-1 ap-southeast-1 ap-southeast-2 eu-central-1 us-east-1 us-east-2 us-west-1 us-west-2; 
do 
  aws s3 sync cloudformation/ s3://stack-drift-notifier-${region}/${RELEASE}/cloudformation --profile ${PROFILE} --region ${region}
  aws s3 sync ${lambda_code_path}/ s3://stack-drift-notifier-${region}/${RELEASE}/${lambda_code_path}/ --exclude "*" --include "${lambda_pkg_name}" --profile ${PROFILE} --region ${region}

done
