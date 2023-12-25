#!/bin/sh

aws cloudformation create-stack --stack-name mcicloudformationstack --template-body file://aws-cli-scripts/mcicloudformation.yaml
