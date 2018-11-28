#!/bin/bash 
set -e
# Set variables
logfile=prep.log
base_home_dir=stack-drift-notifier
lambda_code_path=lambda
lambda_func_name=drift_detection
lambda_pkg_name=${lambda_func_name}.zip
temp_path=${lambda_code_path}/.temp

# Define Usage
function usage()
{
  echo "Usage: $0 {args}"
  echo "Where valid args are: "
  echo "  -b <bucket> (REQUIRED) -- bucket name to sync to"
  echo "  -p <profile> -- Profile to use for AWS commands, defaults to 'default'"
  echo "  -r <release> -- Release variable used for bucket path, defaults to 'master'"
  exit 1
}

# Builds and send the trigger lambda to s3
function build_lambda()
{
  # Make a temp dir to build in 
  mkdir -p ${temp_path}

  # Copy code to the temp path
  cp ${lambda_code_path}/${lambda_func_name}/* ${temp_path}

  # Install requirements to temp path
  cd ${temp_path}
  pip install -r requirements.txt -t .

  # Make a build directory and zip up the build package
  zip -r ../${lambda_pkg_name} ./*

  # Move back home
  numbdirs=$(awk -F"/" '{print NF-1}' <<< "./${temp_path}")
  for i in $(seq 1 ${numbdirs}); do cd ../;done

  # Remove the temparary build dir
  rm -r ${temp_path}

  local_pkg_path=${lambda_code_path}/${lambda_pkg_name}
  aws s3 cp ${local_pkg_path} s3://${BUCKET}/${RELEASE}/${lambda_code_path}/${lambda_pkg_name} --profile ${PROFILE} --exclude *.git/* --exclude *.swp

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
    b)
      BUCKET=$OPTARG
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

echo -e "Starting prep process.\nIf this script does not report success check the log.\nLogs can be found at ${logfile}"
{

# Setup AWS vars
REGION=$(aws configure list --profile ${PROFILE} | grep region | awk '{print $2}')
ACCOUNT_ID=$(aws ec2 describe-security-groups --query 'SecurityGroups[0].OwnerId' --output text --profile ${PROFILE})

# Build your lambda
build_lambda

}  1> $logfile
echo -e "Successfully finished prep.\n  Lambda built and uploaded to s3://${BUCKET}/${RELEASE}/${lambda_code_path}/${lambda_pkg_name}"
